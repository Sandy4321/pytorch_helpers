import abc
from enum import Enum

import numpy as np
import cv2
from imgaug import augmenters as iaa

import torch
from imgaug.parameters import Deterministic


class ImageMaskTransformMode(Enum):
    Image = 1
    Mask = 2


class BaseImageMaskTransformer(object):
    def __init__(self, p=0.5, apply_always=False, apply_image=True, apply_mask=True):
        super(BaseImageMaskTransformer, self).__init__()

        self.p = p
        self.apply_always = apply_always
        self.apply_image = apply_image
        self.apply_mask = apply_mask

    @abc.abstractmethod
    def transform(self, image, mode):
        """Transform the provided object"""

    def __call__(self, image, mask=None):
        if np.random.rand() >= self.p or self.apply_always:

            if self.apply_image:
                image = self.transform(image, mode=ImageMaskTransformMode.Image)

            if self.apply_mask and mask is not None and isinstance(mask, np.ndarray):
                mask = self.transform(mask, mode=ImageMaskTransformMode.Mask)

        if mask is None:
            return image
        else:
            return image, mask


class RandomVerticalFlip(BaseImageMaskTransformer):
    def transform(self, image, mode):
        image = np.flipud(image)
        return image


class RandomHorizontalFlip(BaseImageMaskTransformer):
    def transform(self, image, mode):
        image = np.fliplr(image)
        return image


class RandomTranspose(BaseImageMaskTransformer):
    def transform(self, image, mode):
        transpose_axis = [1, 0]
        if len(image.shape) == 3:
            transpose_axis.append(2)

        image = np.transpose(image, transpose_axis)
        return image


class Resize(BaseImageMaskTransformer):
    def __init__(self, size, **kwargs):
        super(Resize, self).__init__(**kwargs)

        self.size = size

        self.apply_always = True

    def transform(self, image, mode):
        if mode == ImageMaskTransformMode.Image:
            interpolation = cv2.INTER_LINEAR
        else:
            interpolation = cv2.INTER_NEAREST

        image = cv2.resize(image, (self.size, self.size), interpolation=interpolation)

        return image


class CopyNumpy(BaseImageMaskTransformer):
    def __init__(self, **kwargs):
        super(CopyNumpy, self).__init__(**kwargs)

        self.apply_always = True

    def transform(self, image, mode):
        return np.copy(image)


class SamplePatch(BaseImageMaskTransformer):
    def __init__(self, patch_size, **kwargs):
        super(SamplePatch, self).__init__(**kwargs)

        self.patch_size = patch_size

        self.apply_always = True

        self._patch_coordinate_h = 0
        self._patch_coordinate_w = 0

    def transform(self, image, mode):
        # sample coordinates to apply to both image and mask
        if mode == ImageMaskTransformMode.Image:
            image_height = image.shape[0]
            image_width = image.shape[1]

            max_height = image_height - self.patch_size
            max_width = image_width - self.patch_size

            try:
                self._patch_coordinate_h = np.random.randint(0, max_height)
                self._patch_coordinate_w = np.random.randint(0, max_width)
            except ValueError as e:
                print(image.shape, '->', self.patch_size)
                raise e

        c_h = (self._patch_coordinate_h, self._patch_coordinate_h + self.patch_size)
        c_w = (self._patch_coordinate_w, self._patch_coordinate_w + self.patch_size)
        image = image[c_h[0]:c_h[1], c_w[0]:c_w[1]]

        return image


class Add(BaseImageMaskTransformer):
    def __init__(self, from_val=-10, to_val=10, per_channel=0.5, **kwargs):
        super(Add, self).__init__(**kwargs)

        self.from_val = from_val
        self.to_val = to_val
        self.per_channel = per_channel

        self.apply_mask = False

        self._augmentor = iaa.Add((self.from_val, self.to_val), per_channel=self.per_channel)

    def transform(self, image, mode):
        image = self._augmentor.augment_image(image)

        return image


class ContrastNormalization(BaseImageMaskTransformer):
    def __init__(self, from_val=0.8, to_val=1.2, per_channel=0.5, **kwargs):
        super(ContrastNormalization, self).__init__(**kwargs)

        self.from_val = from_val
        self.to_val = to_val
        self.per_channel = per_channel

        self.apply_mask = False

        self._augmentor = iaa.ContrastNormalization((self.from_val, self.to_val), per_channel=self.per_channel)

    def transform(self, image, mode):
        image = self._augmentor.augment_image(image)

        return image


class Rotate(BaseImageMaskTransformer):
    def __init__(self, from_val=-20, to_val=20, mode='reflect', **kwargs):
        super(Rotate, self).__init__(**kwargs)

        self.from_val = from_val
        self.to_val = to_val
        self.mode = mode

        self._augmentor = iaa.Affine(rotate=0, mode=self.mode)

    def transform(self, image, mode):
        # sample angle
        if mode == ImageMaskTransformMode.Image:
            angle = np.random.randint(self.from_val, self.to_val)
            self._augmentor.rotate = Deterministic(angle)

        image = self._augmentor.augment_image(image)

        return image


class Rotate90n(BaseImageMaskTransformer):
    def __init__(self, **kwargs):
        super(Rotate90n, self).__init__(**kwargs)

        self._angles = [0, 90, 180, 270]
        self._augmentor = iaa.Affine(rotate=0)

    def transform(self, image, mode):
        # sample angle
        if mode == ImageMaskTransformMode.Image:
            angle = np.random.choice(self._angles)
            self._augmentor.rotate = Deterministic(angle)

        image = self._augmentor.augment_image(image)

        return image


class Scale(BaseImageMaskTransformer):
    def __init__(self, from_val=0.8, to_val=1.2, mode='reflect', **kwargs):
        super(Scale, self).__init__(**kwargs)

        self.from_val = from_val
        self.to_val = to_val
        self.mode = mode

        self._augmentor = iaa.Affine(scale=1.0, mode=self.mode)

    def transform(self, image, mode):
        # sample angle
        if mode == ImageMaskTransformMode.Image:
            scale = np.random.uniform(self.from_val, self.to_val)
            self._augmentor.scale = Deterministic(scale)

        image = self._augmentor.augment_image(image)

        return image


class MakeBorder(BaseImageMaskTransformer):
    def __init__(self, border_size, **kwargs):
        super(MakeBorder, self).__init__(**kwargs)

        if not isinstance(border_size, tuple):
            border_size = (border_size, border_size, border_size, border_size)

        self.border_size = border_size

        self.apply_always = True
        self.apply_mask = False

    def transform(self, image, mode):
        image = cv2.copyMakeBorder(
            image, self.border_size[0], self.border_size[1], self.border_size[2], self.border_size[3],
            cv2.BORDER_REFLECT
        )

        return image


class Squarify(BaseImageMaskTransformer):
    def __init__(self, **kwargs):
        super(Squarify, self).__init__(**kwargs)

        self.apply_always = True

    def transform(self, image, mode):
        image_size = (image.shape[0], image.shape[1])
        target_size = min(image_size)

        crops = []
        for image_side_size in image_size:
            if image_side_size <= target_size:
                crops.append((0, 0))
                continue

            crop_total = image_side_size - target_size
            crop_before = crop_total // 2
            crop_after = image_side_size - target_size - crop_before
            crops.append((crop_before, crop_after))

        crops.extend([(0, 0) for i in range(len(image.shape) - 2)])

        slices = [slice(a, image.shape[i] - b) for i, (a, b) in enumerate(crops)]
        image = image[slices]

        return image


class ImageMaskTransformsCompose(object):
    def __init__(self, transforms):
        self.transforms = transforms

    def __call__(self, image, mask):
        for transform_step in self.transforms:
            image, mask = transform_step(image, mask)

        return image, mask


class Normalize(object):
    def __init__(self, mean, std, divide=True):
        super(Normalize, self).__init__()

        self.divide = divide
        self.mean = np.reshape(np.array(mean, dtype=np.float32), (1, 1, -1))
        self.std = np.reshape(np.array(std, dtype=np.float32), (1, 1, -1))

    def __call__(self, data):
        if self.divide:
            data = np.divide(data, 255, dtype=np.float32)

        data = np.subtract(data, self.mean, out=data)
        data = np.divide(data, self.std, out=data)

        return data


class ToTensor(object):
    def __init__(self, divide=False, transpose=False, contiguous=False, to_torch=False):
        super(ToTensor, self).__init__()

        self.divide = divide
        self.transpose = transpose
        self.contiguous = contiguous
        self.to_torch = to_torch

    def __call__(self, data):
        if self.transpose:
            data = data.transpose((2, 0, 1))

        if self.contiguous:
            data = np.ascontiguousarray(data)

        if self.divide:
            data = np.divide(data, 255, dtype=np.float32)

        if self.to_torch:
            data = torch.from_numpy(data).float()

        return data
