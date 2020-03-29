"""
MesoNet
Authors: Brandon Forys and Dongsheng Xiao, Murphy Lab
https://github.com/bf777/MesoNet
Licensed under the MIT License (see LICENSE for details)
This file has been adapted from data.py in https://github.com/zhixuhao/unet
"""
from mesonet.utils import natural_sort_key
import numpy as np
import scipy.io as sio
import os
import random
import glob
import skimage.io as io
import skimage.transform as trans
import cv2
import imutils
import scipy
from PIL import Image
import pandas as pd

# Set background colour as black to fix issue with more than one background region being identified.
Background = [0, 0, 0]
# Foreground (cortex) should be rendered as white.
Region = [255, 255, 255]

COLOR_DICT = np.array([Background, Region])


def testGenerator(test_path, num_image=60, target_size=(512, 512), flag_multi_class=False, as_gray=True):
    """
    Import images and resize it to the target size of the model.
    :param test_path: path to input images
    :param num_image: number of input images
    :param target_size: target image size as defined in the Keras model
    :param flag_multi_class: flag the input images as having multiple classes
    :param as_gray: if input image is grayscale, process data input accordingly
    """
    for i in range(num_image):
        img = io.imread(os.path.join(test_path, "%d.png" % i), as_gray=as_gray)
        img = img / 255
        img = trans.resize(img, target_size)
        img = np.reshape(img, img.shape + (1,)) if (not flag_multi_class) else img
        img = np.reshape(img, (1,) + img.shape)
        yield img


def labelVisualize(num_class, color_dict, img):
    """
    Visualize labels on image based on input classes.
    :param num_class: number of classes
    :param color_dict: dictionary of colours defined at top of file
    :param img: input image
    """
    img = img[:, :, 0] if len(img.shape) == 3 else img
    img_out = np.zeros(img.shape + (3,))
    for i in range(num_class):
        img_out[img == i, :] = color_dict[i]
    return img_out / 255


def saveResult(save_path, npyfile, mask_generate, flag_multi_class=False, num_class=2):
    """
    Saves the predicted mask from each brain image to the save folder.
    :param save_path: path to overall folder for saving images
    :param npyfile: results file output after model has made predictions
    :param flag_multi_class: flag the output images as having multiple classes
    :param num_class: if flag_multi_class is True, decide how many classes to categorize each brain image into.
    """
    for i, item in enumerate(npyfile):
        img = labelVisualize(num_class, COLOR_DICT, item) if flag_multi_class else item[:, :, 0]
        io.imsave(os.path.join(save_path, "%d.png" % i), img)


def atlas_to_mask(atlas_path, mask_input_path, mask_warped_path, mask_output_path, n):
    """
    Overlays the U-net mask and a smoothing mask for the cortical boundaries on the transformed brain atlas.
    :param atlas_path: The path to the atlas to be transformed
    :param mask_input_path: The path to the U-net mask corresponding to the input atlas
    :param mask_warped_path: The path to a mask transformed alongside the atlas to correct for gaps between the U-net
    cortical boundaries and the brain atlas.
    :param mask_output_path: The output path of the completed atlas with overlaid masks
    :param n: The number of the current atlas and corresponding transformed mask
    """
    atlas = cv2.imread(atlas_path, cv2.IMREAD_GRAYSCALE)
    mask_input = cv2.imread(mask_input_path, cv2.IMREAD_GRAYSCALE)
    mask_warped = cv2.imread(mask_warped_path, cv2.IMREAD_GRAYSCALE)
    io.imsave(os.path.join(mask_output_path, "{}_mask.png".format(n)), mask_input)
    # Adds the common white regions of the atlas and U-net mask together into a binary image.
    mask_input = cv2.bitwise_and(atlas, mask_input)
    # Adds the common white regions of the mask created above and the corrective mask (correcting for gaps between U-net
    # cortical boundaries and brain atlas) together into a binary image.
    mask_input = cv2.bitwise_and(mask_input, mask_warped)
    io.imsave(os.path.join(mask_output_path, "{}.png".format(n)), mask_input)


def applyMask(image_path, mask_path, save_path, segmented_save_path, mat_save, threshold, git_repo_base, bregma_list,
              region_labels=True):
    """
    Use mask output from model to segment brain image into brain regions, and save various outputs.
    :param image_path: path to folder where brain images are saved
    :param mask_path: path to folder where masks are saved
    :param save_path: path to overall folder for saving all images
    :param segmented_save_path: path to overall folder for saving segmented/labelled brain images
    :param mat_save: choose whether or not to output brain regions to .mat files
    :param threshold: set threshold for segmentation of foregrounds
    :param region_labels: choose whether to est
    """
    image_name_arr = glob.glob(os.path.join(image_path, "*.png"))
    region_bgr_lower = (100, 100, 100)
    region_bgr_upper = (255, 255, 255)
    cnt_array = []
    base_c_max = []
    count = 0
    regions = pd.read_csv(os.path.join(git_repo_base, "atlases/region_labels.csv"))
    # Find the contours of an existing set of brain regions (to be used to identify each new brain region by shape)
    mat_files = glob.glob(os.path.join(git_repo_base, 'atlases/mat_contour_base/*.mat'))
    mat_files.sort(key=natural_sort_key)
    for file in mat_files:
        mat = scipy.io.loadmat(os.path.join(git_repo_base, 'atlases/mat_contour_base/', file))
        mat = mat['vect']
        ret, thresh = cv2.threshold(mat, 5, 255, cv2.THRESH_BINARY)
        io.imsave('cnt_{}.png', thresh)
        base_c = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        base_c = imutils.grab_contours(base_c)
        base_c_max.append(max(base_c, key=cv2.contourArea))
    for i, item in enumerate(image_name_arr):
        bregma_x, bregma_y = bregma_list[i]
        new_data = []
        img = cv2.imread(item)
        mask = cv2.imread(os.path.join(mask_path, "{}.png".format(i)))
        mask = cv2.resize(mask, (img.shape[0], img.shape[1]))
        # Get the region of the mask that is white
        mask_color = cv2.inRange(mask, region_bgr_lower, region_bgr_upper)
        io.imsave(os.path.join(save_path, "{}_mask_binary.png".format(i)), mask_color)
        # Marker labelling
        # noise removal
        kernel = np.ones((3, 3), np.uint8)
        mask_color = np.uint8(mask_color)
        opening = cv2.morphologyEx(mask_color, cv2.MORPH_OPEN, kernel, iterations=1)  # 1
        # sure background area
        sure_bg = cv2.dilate(opening, kernel, iterations=7)  # 7
        # Finding sure foreground area
        dist_transform = cv2.distanceTransform(opening, cv2.DIST_L2, 5)  # 5
        dist_transform = np.uint8(dist_transform)
        ret, sure_fg = cv2.threshold(dist_transform, threshold * dist_transform.max(), 255, 0)
        # Finding unknown region
        sure_fg = np.uint8(sure_fg)
        unknown = cv2.subtract(sure_bg, sure_fg)
        ret, markers = cv2.connectedComponents(sure_fg)
        # Add one to all labels so that sure background is not 0, but 1
        markers = markers + 1
        # Now, mark the region of unknown with zero
        markers[unknown == 255] = 0
        img = np.uint8(img)
        labels = cv2.watershed(img, markers)
        img[labels == -1] = [255, 0, 0]
        labels_x = []
        labels_y = []
        areas = []
        labels_arr = []
        label_jitter = random.randrange(-2, 2)
        for n, label in enumerate(np.unique(labels)):
            label_num = 0
            # if the label is zero, we are examining the 'background'
            # so simply ignore it
            if label == 0:
                continue
            # otherwise, allocate memory for the label region and draw
            # it on the mask
            mask = np.zeros(mask_color.shape, dtype="uint8")
            mask[labels == label] = 255
            # detect contours in the mask and grab the largest one
            cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_NONE)
            cnts = imutils.grab_contours(cnts)
            cnt_array.append(cnts)
            for z, cnt in enumerate(cnts):
                # compute the center of the contour
                if len(cnts) > 1:
                    z = 0
                m = cv2.moments(cnt)
                c_x = int(m["m10"] / m["m00"])
                c_y = int(m["m01"] / m["m00"])
                # compute center relative to bregma
                # rel_x = contour centre x coordinate - bregma x coordinate
                # rel_y = contour centre y coordinate - bregma y coordinate
                rel_x = c_x - bregma_x
                rel_y = c_y - bregma_y
                print("Contour {}: centre ({}, {}), bregma ({}, {})".format(label, rel_x, rel_y, bregma_x, bregma_y))

                c = max(cnts, key=cv2.contourArea)
                # If .mat save checkbox checked in GUI, save contour paths and centre to .mat files for each contour
                if mat_save == 1:
                    mat_save = True
                else:
                    mat_save = False
                # Prepares lists of the contours identified in the brain image, in the order that they are found by
                # OpenCV
                labels_arr.append(label)
                labels_x.append(int(c_x))
                labels_y.append(int(c_y))
                areas.append(cv2.contourArea(c))
                # The first contour just outlines the entire image (which does not provide a useful label or .mat
                # contour) so we'll ignore it
                if label != -1:
                    # Cross-references each contour with a set of contours from a base brain atlas that was manually
                    # labelled with brain regions (as defined in 'region_labels.csv' in the 'atlases' folder). If the
                    # area of the contour is within 5000 square px of the original region and the centre of the contour
                    # is at most 100 px away from the centre of the original contour, label the contour with its
                    # corresponding brain region. Until we figure out how to consistently and accurately label small
                    # brain regions, we only label brain regions with an area greater than 1000 square px.
                    shape_list = []
                    label_color = (0, 0, 255)
                    for n_bc, bc in enumerate(base_c_max):
                        shape_compare = cv2.matchShapes(c, bc, 1, 0.0)
                        shape_list.append(shape_compare)
                    for (n_r, r), (n_bc, bc) in zip(enumerate(regions.itertuples()), enumerate(base_c_max)):
                        min_bc = list(bc[0][0])
                        min_c = list(c[0][0])
                        max_bc = list(bc[0][-1])
                        max_c = list(c[0][-1])

                        # 0.3, 75
                        if label_num == 0 and region_labels and \
                                (min(shape_list) - 0.3 <= cv2.matchShapes(c, bc, 1, 0.0) <= min(shape_list) + 0.3) and \
                                min_bc[0] - 75 <= min_c[0] <= min_bc[0] + 75 and \
                                min_bc[1] - 75 <= min_c[1] <= min_bc[1] + 75 and \
                                max_bc[0] - 75 <= max_c[0] <= max_bc[0] + 75 and \
                                max_bc[1] - 75 <= max_c[1] <= max_bc[1] + 75:
                            # print("Current contour top left corner: {},{}".format(min_c[0], min_c[1]))
                            # print("Baseline contour top left corner: {},{}".format(min_bc[0], min_bc[1]))
                            closest_label = r.name
                            cv2.putText(img, "{} ({})".format(closest_label, r.Index),
                                        (int(c_x + label_jitter), int(c_y + label_jitter)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, label_color, 1)
                            label_num += 1
                        if label_num == 0 and not region_labels:
                            cv2.putText(img, "{}".format(label),
                                        (int(c_x + label_jitter), int(c_y + label_jitter)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, label_color, 1)
                            label_num += 1
                        if mat_save and n > 0:
                            # Create an empty array of the same size as the contour, with the centre of the contour
                            # marked as "255"
                            c_total = np.zeros_like(mask)
                            c_centre = np.zeros_like(mask)
                            # Follow the path of the contour, setting every pixel along the path to 255
                            # Fill in the contour area with 1s
                            cv2.fillPoly(c_total, pts=[c], color=(255, 255, 255))
                            # Set the contour's centroid to 255
                            if c_x < mask.shape[0] and c_y < mask.shape[0]:
                                c_centre[c_x, c_y] = 255
                            if not os.path.isdir(os.path.join(segmented_save_path, 'mat_contour')):
                                os.mkdir(os.path.join(segmented_save_path, 'mat_contour'))
                            if not os.path.isdir(os.path.join(segmented_save_path, 'mat_contour_centre')):
                                os.mkdir(os.path.join(segmented_save_path, 'mat_contour_centre'))
                            sio.savemat(os.path.join(segmented_save_path,
                                                     'mat_contour/roi_{}_{}_{}'.format(i, r.Index, z)),
                                        {'vect': c_total})
                            sio.savemat(os.path.join(segmented_save_path,
                                                     'mat_contour_centre/roi_centre_{}_{}_{}'.format(i, r.Index, z)),
                                        {'vect': c_centre})
            count += 1
        io.imsave(os.path.join(segmented_save_path, "{}_mask_segmented.png".format(i)), img)
        img_edited = Image.open(os.path.join(save_path, "{}_mask_binary.png".format(i)))
        # Generates a transparent version of the brain atlas.
        img_rgba = img_edited.convert("RGBA")
        data = img_rgba.getdata()
        for pixel in data:
            if pixel[0] == 255 and pixel[1] == 255 and pixel[2] == 255:
                new_data.append((pixel[0], pixel[1], pixel[2], 0))
            else:
                new_data.append(pixel)
        img_rgba.putdata(new_data)
        img_rgba.save(os.path.join(save_path, "{}_mask_transparent.png".format(i)))
        img_transparent = cv2.imread(os.path.join(save_path, "{}_mask_transparent.png".format(i)))
        img_trans_for_mat = np.uint8(img_transparent)
        if mat_save == 1:
            sio.savemat(os.path.join(segmented_save_path, 'mat_contour/transparent_{}'.format(i)),
                        {'vect': img_trans_for_mat})
        masked_img = cv2.bitwise_and(img, img_transparent, mask=mask_color)
        io.imsave(os.path.join(save_path, "{}_overlay.png".format(i)), masked_img)
        print("Mask {} saved!".format(i))
        d = {'region': labels_arr, 'x': labels_x, 'y': labels_y, 'area': areas}
        df = pd.DataFrame(data=d)
        df.to_csv("{}_region_labels_new.csv".format(i))
    print('Analysis complete! Check the outputs in the folders of {}.'.format(save_path))
    os.chdir('../..')
