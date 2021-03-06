"""
 Evaluate the model
 - Mostly inherited from Stanford CS230 example code:
   https://github.com/cs230-stanford/cs230-code-examples/tree/master/pytorch/vision

"""

import argparse
import logging
import os

import numpy as np
import torch
import torch.nn.functional as F
from torch.autograd import Variable
import utils
import model.net as net
import model.data_loader as data_loader

# from tensorboardX import SummaryWriter

parser = argparse.ArgumentParser()
parser.add_argument('--data_dir'    , default='datasets/spec_split'   , help="Directory containing the splitted dataset")
parser.add_argument('--model_dir'   , default='experiments/base_model', help="Directory containing params.json")
parser.add_argument('--num_classes' , default=300, type=int, help="Numer of classes as in splitting datasets")
parser.add_argument('--restore_file', default='best', help="name of the file in --model_dir \
                     containing weights to load")

# writer = SummaryWriter('tensorboardlogs/vallog')

def evaluate(model, loss_fn, dataloader, metrics, params, num_classes, epoch, logger, eva=False):
    """Evaluate the model on `num_steps` batches.

    Args:
        model: (torch.nn.Module) the neural network
        loss_fn: a function that takes batch_output and batch_labels and computes the loss for the batch
        dataloader: (DataLoader) a torch.utils.data.DataLoader object that fetches data
        metrics: (dict) a dictionary of functions that compute a metric using the output and labels of each batch
        params: (Params) hyperparameters
        num_steps: (int) number of batches to train on, each of size params.batch_size
    """

    # set model to evaluation mode
    model.eval()

    # summary for current eval loop
    summ = []

    # compute metrics over the dataset
    cm = []
    for i, (data_batch, labels_batch) in enumerate(dataloader):
        # move to GPU if available
        if params.cuda:
            data_batch, labels_batch = data_batch.cuda(async=True), labels_batch.cuda(async=True)
        # fetch the next evaluation batch
        data_batch, labels_batch = Variable(data_batch), Variable(labels_batch)
        
        # compute model output
        output_batch = model(data_batch)
        loss = loss_fn(output_batch.float(), labels_batch.float())

        # compute all metrics on this batch
        summary_batch = {metric: metrics[metric](output_batch, labels_batch, params.threshold)
                         for metric in metrics}
        summary_batch['loss'] = loss.data[0]
        summ.append(summary_batch)

        if i % params.save_summary_steps == 0:
            ## tensorboard logging
            niter = epoch*len(dataloader)+i
            for tag, value in summary_batch.items():
                logger.scalar_summary(tag, value, niter)
                # writer.add_scalar(tag, value, niter)

        if hasattr(params,'if_single'): 
            if params.if_single == 1: # single-label
                cm.append(utils.confusion_matrix(output_batch, labels_batch))

    ## confusion matrix
    if hasattr(params,'if_single'): 
        if params.if_single == 1: # single-label
            cm = np.array(cm)
            cm = np.mean(cm, axis=0)
            if eva: # if on test set
                np.save('./cm_test/cm.npy',cm)
            else:
                np.save('./cm_val/cm{}.npy'.format(str(epoch).zfill(3)),cm)

    # compute mean of all metrics in summary
    metrics_mean = {metric:np.mean([x[metric] for x in summ]) for metric in summ[0]} 
    metrics_string = " ; ".join("{}: {:05.3f}".format(k, v) for k, v in metrics_mean.items())
    logging.info("- Eval metrics : " + metrics_string)

    return metrics_mean


if __name__ == '__main__':
    """
        Evaluate the model on the test set.
    """
    # Load the parameters
    args = parser.parse_args()
    json_path = os.path.join(args.model_dir, 'params.json')
    assert os.path.isfile(json_path), "No json configuration file found at {}".format(json_path)
    params = utils.Params(json_path)

    # use GPU if available
    params.cuda = torch.cuda.is_available()     # use GPU is available

    # Set the random seed for reproducible experiments
    torch.manual_seed(230)
    if params.cuda: torch.cuda.manual_seed(230)
        
    # Get the logger
    utils.set_logger(os.path.join(args.model_dir, 'evaluate.log'))

    # Create the input data pipeline
    logging.info("Creating the dataset...")

    # fetch dataloaders
    if hasattr(params,'if_single'): 
        if params.if_single == 1: # single-label
            dataloaders = data_loader.fetch_dataloader(['test'], args.data_dir, params, mixing=False)
    else:
        dataloaders = data_loader.fetch_dataloader(['test'], args.data_dir, params)
    test_dl = dataloaders['test']

    logging.info("- done.")

    # Define the model
    if params.model == 1:
        model = net.DenseNetBase(params,args.num_classes).cuda() if params.cuda else net.DenseNetBase(params,args.num_classes)
    elif params.model == 2:
        model = net.SqueezeNetBase(params,args.num_classes).cuda() if params.cuda else net.DenseNetBase(params,args.num_classes)
    elif params.model == 3:
        model = net.InceptionBase(params,args.num_classes).cuda() if params.cuda else net.InceptionBase(params,args.num_classes)
    elif params.model == 4:
        model = net.InceptionResnetBase(params,args.num_classes).cuda() if params.cuda else net.InceptionResnetBase(params,args.num_classes)
    elif params.model == 5:
        model = net.ResNet14(params,args.num_classes).cuda() if params.cuda else net.ResNet14(params,args.num_classes)
    elif params.model == 6:
        model = net.DenseBR(params,args.num_classes).cuda() if params.cuda else net.DenseBR(params,args.num_classes)
    elif params.model == 7:
        model = net.ResBR(params,args.num_classes).cuda() if params.cuda else net.ResBR(params,args.num_classes)
    elif params.model == 8:
        model = net.DenseNetBLSTM(params,args.num_classes).cuda() if params.cuda else net.DenseNetBLSTM(params,args.num_classes)

    # fetch loss function and metrics
    if hasattr(params,'if_single'): 
        if params.if_single == 1: # single-label
            loss_fn = net.loss_fn_sing
            metrics = net.metrics_sing
    else:
        if hasattr(params,'loss_fn'):
            if params.loss_fn == 1: # use WARP loss
                print('  ---loss function is WARP'); print('')
                loss_fn = net.loss_warp
            elif params.loss_fn == 2: # use LSEP loss
                print('  ---loss function is LSEP'); print('')
                loss_fn = net.loss_lsep
        else:
            print('  ---loss function is BCE'); print('')
            loss_fn = net.loss_fn
        metrics = net.metrics
    
    logging.info("Starting evaluation")

    # Reload weights from the saved file
    utils.load_checkpoint(os.path.join(args.model_dir, args.restore_file + '.pth.tar'), model)

    # Evaluate
    test_metrics = evaluate(model, loss_fn, test_dl, metrics, params, args.num_classes, 1, eva=True)
    save_path = os.path.join(args.model_dir, "metrics_test_{}.json".format(args.restore_file))
    utils.save_dict_to_json(test_metrics, save_path)
