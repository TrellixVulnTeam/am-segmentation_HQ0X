import logging
import tarfile
from collections import namedtuple
from functools import partial, wraps
from pathlib import Path
from shutil import rmtree
from time import time

import cv2
import torch
import torch.nn as nn
import segmentation_models_pytorch as smp

logger = logging.getLogger('am-segm')


def min_max(a):
    return a.min(), a.max()


def dict_to_namedtuple(dic):
    return namedtuple('Metrics', dic.keys())(**dic)


def clean_dir(path):
    logger.info(f'Cleaning up {path} directory')
    rmtree(path, ignore_errors=True)
    Path(path).mkdir(parents=True, exist_ok=True)


def time_it(func):

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time()
        res = func(*args, **kwargs)
        minutes, seconds = divmod(time() - start, 60)
        func_name = func.func.__name__ if isinstance(func, partial) else func.__name__
        logger.info(f"Function '{func_name}' running time: {minutes:.0f}m {seconds:.0f}s")
        return res

    return wrapper


def save_model(model, model_path):
    logger.info(f'Saving model to {model_path}')
    model_path = Path(model_path)
    model_path.parent.mkdir(exist_ok=True)
    torch.save(model.state_dict(), model_path)


def load_model(model_path):
    logger.info(f'Loading model from "{model_path}"')

    device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
    model = smp.Unet(
        encoder_name='se_resnext50_32x4d', encoder_weights=None, decoder_use_batchnorm=True
    )
    if torch.cuda.device_count() > 1:
        logger.info("Gpu count: {}".format(torch.cuda.device_count()))
        model = nn.DataParallel(model)

    with open(model_path, 'rb') as f:
        model.load_state_dict(torch.load(f, map_location=device))
    model.eval()
    return model.to(device)


def find_all_groups(data_path):
    return [p.name for p in (data_path / 'source').iterdir()]


def iterate_groups(input_path, output_path=None, groups=None, func=None):
    assert func, '"func" should be provided'

    for group in groups or [p.name for p in input_path.iterdir()]:
        try:
            if output_path:
                func(input_path / group, output_path / group)
            else:
                func(input_path / group)
        except Exception as e:
            func_name = func.func.__name__ if isinstance(func, partial) else func.__name__
            logger.error(
                f'Failed to process {input_path / group} path with {func_name} function',
                exc_info=True
            )
