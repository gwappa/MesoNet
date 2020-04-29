"""
MesoNet
Authors: Brandon Forys and Dongsheng Xiao, Murphy Lab
https://github.com/bf777/MesoNet
Licensed under the MIT License (see LICENSE for details)
This file has been adapted from main.py in https://github.com/zhixuhao/unet
"""
from mesonet.model import *
from mesonet.data import *
import numpy as np
from keras.callbacks import ModelCheckpoint
from mesonet.utils import parse_yaml


def trainModel(input_file, model_name, log_folder, git_repo_base, steps_per_epoch, epochs):
    """
    Trains a U-Net model based on the brain images and corresponding masks supplied to input_file
    :param input_file: A directory containing an 'image' folder with brain images, and a 'label' folder with
    corresponding masks to segment these brain images.
    :param model_name: The name of the new U-net model to be created.
    :param steps_per_epoch: During U-Net training, the number of steps that the model will take per epoch. Defaults to
    300 steps per epoch.
    :param git_repo_base: The path to the base git repository containing necessary resources for MesoNet (reference
    atlases, DeepLabCut config files, etc.)
    :param epochs: During U-Net training, the number of epochs for which the model will run. Defaults to 60 epochs (set
    lower for online learning, e.g. if augmenting existing model).
    :param log_folder: The folder to which the performance of the model should be logged.
    :return:
    """
    data_gen_args = dict(rotation_range=0.3, width_shift_range=0.05, height_shift_range=0.05, shear_range=0.05,
                         zoom_range=0.05, horizontal_flip=True, fill_mode='nearest')
    myGene = trainGenerator(2, input_file, 'image', 'label', data_gen_args, save_to_dir=None)
    model = unet()
    model_checkpoint = ModelCheckpoint(model_name, monitor='loss', verbose=1, save_best_only=True)
    history_callback = model.fit_generator(myGene, steps_per_epoch=steps_per_epoch, epochs=epochs,
                                           callbacks=[model_checkpoint])
    loss_history = history_callback.history["loss"]
    acc_history = history_callback.history["acc"]
    np_loss_hist = np.array(loss_history)
    np_acc_hist = np.array(acc_history)
    np.savetxt(os.path.join(log_folder, "loss_history.csv"), np_loss_hist, delimiter=",")
    np.savetxt(os.path.join(log_folder, "acc_history.csv"), np_acc_hist, delimiter=",")
    model.save(os.path.join(git_repo_base, 'models', model_name))


def train_model(config_file):
    """
    Loads parameters into trainModel from config file.
    :param config_file: The full path to a MesoNet config file (generated using mesonet.config_project())
    :return:
    """
    cfg = parse_yaml(config_file)
    input_file = cfg['input_file']
    model_name = cfg['model_name']
    log_folder = cfg['log_folder']
    git_repo_base = cfg['git_repo_base']
    steps_per_epoch = cfg['steps_per_epoch']
    epochs = cfg['epochs']
    trainModel(input_file, model_name, log_folder, git_repo_base, steps_per_epoch, epochs)
