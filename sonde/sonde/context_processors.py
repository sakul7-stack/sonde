from . import config


def site_config(request):
    return {
        "SITE_BASE_URL": config.SITE_BASE_URL,
        "API_SONDES_URL": config.API_SONDES_URL,
        "API_PRED_URL": config.API_PRED_URL,
        "PREDICT_PROX_URL": config.PREDICT_PROX_URL,
        "DATA_SKEW_T_URL": config.DATA_SKEW_T_URL,
        "DATA_HODO_URL": config.DATA_HODO_URL,
        "DATA_ATMOS_URL": config.DATA_ATMOS_URL,
        "CESIUM_TOKEN": config.CESIUM_TOKEN,
    }
