from swift.common.swob import HTTPMethodNotAllowed, Response
from swift.common.utils import public
from vertigo_middleware.handlers import VertigoBaseHandler
from vertigo_middleware.common.utils import get_microcontroller_list_object
from vertigo_middleware.common.utils import set_microcontroller_object
from vertigo_middleware.common.utils import delete_microcontroller_object
import time


class VertigoObjectHandler(VertigoBaseHandler):

    def __init__(self, request, conf, app, logger):
        super(VertigoObjectHandler, self).__init__(
            request, conf, app, logger)

    def _parse_vaco(self):
        _, _, acc, cont, obj = self.request.split_path(
            5, 5, rest_with_last=True)
        return ('v1', acc, cont, obj)

    def handle_request(self):
        if hasattr(self, self.request.method) and self.is_valid_request:
            try:
                handler = getattr(self, self.request.method)
                getattr(handler, 'publicly_accessible')
            except AttributeError:
                return HTTPMethodNotAllowed(request=self.request)
            return handler()
        else:
            return self.request.get_response(self.app)
            # return HTTPMethodNotAllowed(request=self.request)

    def _process_mc_data(self, response, mc_data):
        """
        Processes the data returned from the microcontroller
        """
        if mc_data['command'] == 'CONTINUE':
            return response

        elif mc_data['command'] == 'STORLET':
            slist = mc_data['list']
            self.logger.info('Vertigo - Go to execute Storlets: ' + str(slist))
            return self.apply_storlet_on_get(response, slist)

        elif mc_data['command'] == 'CANCEL':
            msg = mc_data['message']
            return Response(body=msg + '\n', headers={'etag': ''},
                            request=self.request)

    @public
    def GET(self):
        """
        GET handler on Object
        """
        response = self.request.get_response(self.app)

        # start = time.time()

        if self.obj.endswith('/'):
            # is a pseudo-folder
            mc_list = None
        else:
            mc_list = get_microcontroller_list_object(response.headers, self.method)

        if mc_list:
            self.logger.info('Vertigo - There are microcontrollers' +
                             ' to execute: ' + str(mc_list))
            self._setup_docker_gateway(response)
            mc_data = self.mc_docker_gateway.execute_microcontrollers(mc_list)
            response = self._process_mc_data(response, mc_data)
        else:
            self.logger.info('Vertigo - No microcontrollers to execute')

        # end = time.time() - start
        # f = open("/tmp/vertigo/vertigo_get_overhead.log", 'a')
        # f.write(str(int(round(end * 1000)))+'\n')
        # f.close()

        return response

    @public
    def PUT(self):
        """
        PUT handler on Object
        """
        if self.is_trigger_assignation:
            trigger, micro_controller = self.get_mc_assignation_data()

            try:
                set_microcontroller_object(self, trigger, micro_controller)
                msg = 'Vertigo - Microcontroller "' + micro_controller + \
                    '" correctly assigned to the "' + trigger + '" trigger.\n'
            except ValueError as e:
                msg = e.args[0]
            self.logger.info(msg)

            response = Response(body=msg, headers={'etag': ''},
                                request=self.request)

        elif self.is_trigger_deletion:
            trigger, micro_controller = self.get_mc_deletion_data()

            try:
                delete_microcontroller_object(self, trigger, micro_controller)
                msg = 'Vertigo - Microcontroller "' + micro_controller +\
                    '" correctly removed from the "' + trigger + '" trigger.\n'
            except ValueError as e:
                msg = e.args[0]

            response = Response(body=msg, headers={'etag': ''},
                                request=self.request)

        elif self.request.headers['Content-Type'] == 'vertigo/link':
            response = self.request.get_response(self.app)
            response.headers['Content-Type'] = 'vertigo/link'

        else:
            response = self.request.get_response(self.app)

        return response
