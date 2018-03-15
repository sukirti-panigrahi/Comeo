from .common import *


DEBUG = True
TEMPLATE_DEBUG = True
ALLOWED_HOSTS = ["localhost"]

STATIC_URL = '/static/'

INSTALLED_APPS += ('debug_toolbar', 'django_extensions', 'apps.comeo_debug')

EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
EMAIL_FILE_PATH = 'email-dummy/'

CKEDITOR_UPLOAD_PATH = "ckeditor/"
CKEDITOR_IMAGE_BACKEND = "pillow"

PSP_MERCHANT_ID = '<PLEASE SET_MERCHANT_ID>'
PSP_API_URL = 'https://wl1-api-dev-domnl.gingerpayments.com/v1'
PSP_API_KEY = '<PLEASE SET API KEY'
PAYMENT_RETURN_URL = 'http://localhost/crowdfunding/ginger_return_redirect/?campaign_pk={}'

# django debug toolbar configuration
def show_toolbar(request):
    return True
DEBUG_TOOLBAR_CONFIG = {
    # needed to skip INTERNAL_IPS check, which depends on Docker machine ip
    "SHOW_TOOLBAR_CALLBACK": show_toolbar,
}

# ipython
# SHELL_PLUS_PRE_IMPORTS = (
#     ('module.submodule1', ('class1', 'function2')),
#     ('module.submodule2', 'function3'),
#     ('module.submodule3', '*'),
#     'module.submodule4'
# )
