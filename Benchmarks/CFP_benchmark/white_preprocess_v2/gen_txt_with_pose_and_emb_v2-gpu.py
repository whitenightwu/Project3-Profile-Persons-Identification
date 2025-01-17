from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import time
import tensorflow as tf
import numpy as np
import sys
import os
import argparse
import facenet
import cv2
from deepgaze.head_pose_estimation import CnnHeadPoseEstimator
import torch
import torch.nn as nn
from torch.autograd import Variable
from torch.utils.data import DataLoader
from torchvision import transforms
import torch.backends.cudnn as cudnn
import torchvision
import torch.nn.functional as F
from PIL import Image

import datasets, hopenet, utils

def main(args):
    train_set = facenet.get_dataset(args.data_dir)
    image_list, label_list = facenet.get_image_paths_and_labels(train_set)
    # fetch the classes (labels as strings) exactly as it's done in get_dataset
    path_exp = os.path.expanduser(args.data_dir)

    classes_name = []
    img_name = []
    for path in os.listdir(path_exp):
        # if os.path.isdir(path):
        for tpath in os.listdir(os.path.join(path_exp, path)):
            classes_name.append(path)
            img_name.append(tpath)



    gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=args.gpu_memory_fraction)
    sess_2 = tf.Session(config=tf.ConfigProto(gpu_options=gpu_options))

    cudnn.enabled = True

    snapshot_path = "/home/ydwu/project3/reference/deep-head-pose/snapshot/hopenet_robust_alpha1.pkl"

    # ResNet50 structure
    model = hopenet.Hopenet(torchvision.models.resnet.Bottleneck, [3, 4, 6, 3], 66)

    saved_state_dict = torch.load(snapshot_path)
    # saved_state_dict = torch.load(snapshot_path, map_location=lambda storage, loc: storage)
    model.load_state_dict(saved_state_dict)
    model.cuda(0)

    # Test the Model
    model.eval()  # Change model to 'eval' mode (BN uses moving mean/var).
    total = 0

    transformations = transforms.Compose([transforms.Scale(224),
                                          transforms.CenterCrop(224), transforms.ToTensor(),
                                          transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])])



    with tf.Graph().as_default():

        # Start running operations on the Graph.
        gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=args.gpu_memory_fraction)
        sess = tf.Session(config=tf.ConfigProto(gpu_options=gpu_options))


        # with tf.Session() as sess:
        with sess.as_default():

            # Load the model
            facenet.load_model(args.model_dir)

            # Get input and output tensors
            images_placeholder = tf.get_default_graph().get_tensor_by_name("input:0")
            embeddings = tf.get_default_graph().get_tensor_by_name("embeddings:0")
            phase_train_placeholder = tf.get_default_graph().get_tensor_by_name("phase_train:0")

            # Run forward pass to calculate embeddings
            nrof_images = len(image_list)
            print('Number of images: ', nrof_images)
            batch_size = args.image_batch
            if nrof_images % batch_size == 0:
                nrof_batches = nrof_images // batch_size
            else:
                nrof_batches = (nrof_images // batch_size) + 1
            print('Number of batches: ', nrof_batches)
            embedding_size = embeddings.get_shape()[1]
            emb_array = np.zeros((nrof_images, embedding_size))
            pose_array = np.zeros((nrof_images, 3))
            start_time = time.time()

            for i in range(nrof_batches):
                if i == nrof_batches -1:
                    n = nrof_images
                else:
                    n = i*batch_size + batch_size

                # Get images for the batch
                # images = facenet.load_data(image_list[i*batch_size:n], False, False, args.image_size)
                images, pose = facenet.ydwu_load_data_gpu(image_list[i * batch_size:n], False, False, args.image_size, transformations, model)
                # print("pose = ", pose)
                pose_array[i * batch_size:n, :] = pose

                feed_dict = { images_placeholder: images, phase_train_placeholder:False }

                # Use the facenet model to calcualte embeddings
                embed = sess.run(embeddings, feed_dict=feed_dict)
                # print("embed = ", embed)
                emb_array[i*batch_size:n, :] = embed
                print('Completed batch', i+1, 'of', nrof_batches)


                ydwu_image_list = image_list[i * batch_size:n]

                aaa = pose.tolist()
                bbb = embed.tolist()
                ff = open('/home/ydwu/project3/v2_pose_and_emb.txt', 'a')


                # for jj in range(i * batch_size, n):
                    # ff.write(classes_name[jj] + ' ')
                    # ff.write(img_name[jj] + ' ')

                for jj in range(len(ydwu_image_list)):
                    # # ydwu_class = str(ydwu_image_list[jj]).split("/")[-2]
                    # # ydwu_img = str(ydwu_image_list[jj]).split("/")[-1]
                    # ff.write(str(ydwu_image_list[jj]).split("/")[-2] + ' ')
                    # ff.write(str(ydwu_image_list[jj]).split("/")[-1] + ' ')
                    # ff.write(str(aaa[jj]).strip('[').strip(']').replace(',', '') + ' ')
                    # ff.write(str(bbb[jj]).strip('[').strip(']').replace(',', '') + '\n')
                    ff.write(str(ydwu_image_list[jj]).split("/")[-2] + ' ')
                    ff.write(str(ydwu_image_list[jj]).split("/")[-1] + ' ')
                    ff.write(str(aaa[jj]) + ' ')
                    ff.write(str(bbb[jj]) + '\n')

                ff.close()

            run_time = time.time() - start_time
            print('Run time: ', run_time)

            #   export emedings and labels
            label_list  = np.array(label_list)


def parse_arguments(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--model_dir', type=str,
                        default='/home/ydwu/project3/00-del/squeezenet',
        help='Directory containing the meta_file and ckpt_file')

    parser.add_argument('--data_dir', type=str,
                        default = '/home/ydwu/project3/00-del/white-lfw',
        help='Directory containing images. If images are not already aligned and cropped include --is_aligned False.')
    #default='/home/ydwu/project3/zihui_DREAM/preprocess/white-lfw',
    # default = '/home/ydwu/project3/00-del/white-lfw',
    # default = '/media/ydwu/Document/Datasets/white-ms1mclean',

    parser.add_argument('--image_size', type=int,
        help='Image size (height, width) in pixels.', default=160)
    parser.add_argument('--image_batch', type=int,
        help='Number of images stored in memory at a time. Default 500.',
        default=77)
    parser.add_argument('--gpu_memory_fraction', type=float,
        help='Upper bound on the amount of GPU memory that will be used by the process.', default=0.4)

    #   numpy file Names
    parser.add_argument('--embeddings_name', type=str,
        help='Enter string of which the embeddings numpy array is saved as.',
        default='embeddings.npy')
    parser.add_argument('--labels_name', type=str,
        help='Enter string of which the labels numpy array is saved as.',
        default='labels.npy')
    parser.add_argument('--labels_strings_name', type=str,
        help='Enter string of which the labels as strings numpy array is saved as.',
        default='label_strings.npy')

    return parser.parse_args(argv)

if __name__ == '__main__':
    main(parse_arguments(sys.argv[1:]))
