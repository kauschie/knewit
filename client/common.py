import logging

logging.basicConfig(filename='logs/host_log.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.debug("Logger module loaded from common.")