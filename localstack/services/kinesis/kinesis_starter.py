import logging
import traceback
from localstack import config
from localstack.services import install
from localstack.constants import MODULE_MAIN_PATH
from localstack.utils.aws import aws_stack
from localstack.utils.common import mkdir, get_free_tcp_port, replace_in_file
from localstack.services.infra import start_proxy_for_service, do_run, log_startup_message

LOGGER = logging.getLogger(__name__)


def appy_patches():
    files = [
        '%s/node_modules/kinesalite/validations/decreaseStreamRetentionPeriod.js',
        '%s/node_modules/kinesalite/validations/increaseStreamRetentionPeriod.js'
    ]
    for file_path in files:
        file_path = file_path % MODULE_MAIN_PATH
        replace_in_file('lessThanOrEqual: 168', 'lessThanOrEqual: 8760', file_path)


def start_kinesis(port=None, asynchronous=False, update_listener=None):
    # install and apply patches
    install.install_kinesalite()
    appy_patches()
    # start up process
    port = port or config.PORT_KINESIS
    backend_port = get_free_tcp_port()
    latency = config.KINESIS_LATENCY
    kinesis_data_dir_param = ''
    if config.DATA_DIR:
        kinesis_data_dir = '%s/kinesis' % config.DATA_DIR
        mkdir(kinesis_data_dir)
        kinesis_data_dir_param = '--path %s' % kinesis_data_dir
    cmd = (
        '%s/node_modules/kinesalite/cli.js --shardLimit %s --port %s'
        ' --createStreamMs %s --deleteStreamMs %s --updateStreamMs %s %s'
    ) % (
        MODULE_MAIN_PATH, config.KINESIS_SHARD_LIMIT, backend_port,
        latency, latency, latency, kinesis_data_dir_param
    )
    log_startup_message('Kinesis')
    start_proxy_for_service('kinesis', port, backend_port, update_listener)
    return do_run(cmd, asynchronous)


def check_kinesis(expect_shutdown=False, print_error=False):
    out = None
    try:
        # check Kinesis
        out = aws_stack.connect_to_service(service_name='kinesis').list_streams()
    except Exception as e:
        if print_error:
            LOGGER.error('Kinesis health check failed: %s %s' % (e, traceback.format_exc()))
    if expect_shutdown:
        assert out is None
    else:
        assert isinstance(out['StreamNames'], list)
