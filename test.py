from __future__ import print_function
import sys
import os
import argparse
import torch
import torch.nn as nn
import torch.backends.cudnn as cudnn
import torchvision.transforms as transforms
from torch.autograd import Variable
from data import VOC_ROOT, VOC_CLASSES as labelmap
#from data import GTDB_ROOT, GTDB_CLASSES as labelmap
from PIL import Image
from data import *
import torch.utils.data as data
from ssd import build_ssd
from utils import draw_boxes, helpers

parser = argparse.ArgumentParser(description='Single Shot MultiBox Detection')
parser.add_argument('--trained_model', default='weights/ssd300_GTDB_990.pth',
                    type=str, help='Trained state_dict file path to open')
parser.add_argument('--save_folder', default='eval/', type=str,
                    help='Dir to save results')
parser.add_argument('--visual_threshold', default=0.6, type=float,
                    help='Final confidence threshold')
parser.add_argument('--cuda', default=False, type=bool,
                    help='Use cuda to train model')
parser.add_argument('--dataset_root', default=VOC_ROOT, help='Location of VOC root directory')
parser.add_argument('-f', default=None, type=str, help="Dummy arg so we can load in Jupyter Notebooks")
args = parser.parse_args()

if args.cuda and torch.cuda.is_available():
    torch.set_default_tensor_type('torch.cuda.FloatTensor')
else:
    torch.set_default_tensor_type('torch.FloatTensor')

if not os.path.exists(args.save_folder):
    os.mkdir(args.save_folder)


def test_net(save_folder, net, cuda, gpu_id, testset, transform, thresh):
    # dump predictions and assoc. ground truth to text file for now
    filename = save_folder + 'detection_output.txt'
    if os.path.isfile(filename):
        os.remove(filename)

    #num_images = len(testset)

    f = open(filename, "w")

    ## TODO remove this line
    num_images = 200
    for i in range(num_images):
        print('Testing image {:d}/{:d}....'.format(i+1, num_images))
        img = testset.pull_image(i)
        img_id, annotation = testset.pull_anno(i, 'test')
        x = torch.from_numpy(transform(img)[0]).permute(2, 0, 1)
        x = x.unsqueeze(0)

        f.write('\nFOR: '+img_id+'\n')
        for box in annotation:
            f.write('label: '+' || '.join(str(b) for b in box)+'\n')
        if cuda:
            x = x.to(gpu_id)

        y, debug_boxes, debug_scores = net(x)      # forward pass
        detections = y.data
        # scale each detection back up to the image
        scale = torch.Tensor([img.shape[1], img.shape[0],
                             img.shape[1], img.shape[0]])
        pred_num = 0

        recognized_boxes = []
        #[1,2,200,5] -> 1 is number of classes, 200 is top_k, 5 is bounding box with class label,
        for i in range(detections.size(1)):
            j = 0
            while j < detections.size(2) and detections[0, i, j, 0] >= thresh: #TODO it was 0.6
                if pred_num == 0:
                    f.write('PREDICTIONS: '+'\n')
                score = detections[0, i, j, 0]
                label_name = labelmap[i-1]
                pt = (detections[0, i, j, 1:]*scale).cpu().numpy()
                coords = (pt[0], pt[1], pt[2], pt[3])
                recognized_boxes.append(coords)
                #confs.append(score)
                pred_num += 1
                f.write(str(pred_num)+' label: '+label_name+' score: ' +
                        str(score) + ' '+' || '.join(str(c) for c in coords) + '\n')
                j += 1

        draw_boxes(img, recognized_boxes, debug_boxes, debug_scores, scale, os.path.join("eval", img_id + ".png"))

    f.close()

def test_voc():
    # load net
    num_classes = len(VOC_CLASSES) + 1 # +1 background
    net = build_ssd('test', 300, num_classes) # initialize SSD
    net.load_state_dict(torch.load(args.trained_model))
    net.eval()
    print('Finished loading model!')
    # load data
    testset = VOCDetection(args.dataset_root, [('2007', 'test')], None, VOCAnnotationTransform())
    if args.cuda:
        net = net.cuda()
        cudnn.benchmark = True
    # evaluation
    test_net(args.save_folder, net, args.cuda, testset,
             BaseTransform(net.size, (104, 117, 123)),
             thresh=args.visual_threshold)


def test_gtdb():

    gpu_id = 0
    if args.cuda:
        gpu_id = helpers.get_freer_gpu()
        torch.cuda.set_device(gpu_id)

    # load net
    num_classes = 2 # +1 background
    net = build_ssd('test', gtdb, gpu_id, 300, num_classes) # initialize SSD
    net.to(gpu_id)
    net.load_state_dict(torch.load(args.trained_model, map_location={'cuda:0':'cuda:1'}))
    net.eval()
    print('Finished loading model!')
    # load data
    testset = GTDBDetection(args.dataset_root, 'processed_test', None, GTDBAnnotationTransform())
    #testset = GTDBDetection(args.dataset_root, 'processed_train', None, GTDBAnnotationTransform())

    if args.cuda:
        net = net.to(gpu_id)
        cudnn.benchmark = True

    # evaluation
    test_net(args.save_folder, net, args.cuda, gpu_id, testset,
             BaseTransform(net.size, (104, 117, 123)),
             thresh=args.visual_threshold)

if __name__ == '__main__':
    #test_voc()
    #os.environ['CUDA_VISIBLE_DEVICES'] = '1'
    #torch.cuda.set_device(1)
    test_gtdb()
