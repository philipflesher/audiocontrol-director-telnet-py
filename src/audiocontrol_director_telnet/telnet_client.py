"""Something"""

import telnetlib3
#from telnetlib import IAC, WILL, DONT, ECHO

class InputID():
    """Represents an input, which can be either an analog stereo input or a digital stereo input"""
    def __init__(self):
        self._analog = ''
        self._digital = ''

    @classmethod
    def create_analog(cls, selection: int):
        """Analog stereo input options are 1-8, inclusive"""
        instance = InputID()
        instance._analog = selection
        return instance

    @classmethod
    def create_digital(cls, selection: str):
        """Digital stereo input options are 'a' or 'b'"""
        instance = InputID()
        instance._digital = selection
        return instance

    @classmethod
    def create_from_status_id(cls, status_id: str):
        """Create instance from status ID string"""
        status_parts = status_id.split(' & ')
        numeric_id = int(status_parts[1])
        instance = InputID()
        if numeric_id >= 1 and numeric_id <= 8:
            instance._analog = numeric_id
        else:
            instance._digital = 'a' if numeric_id == 9 else 'b'
        return instance

    def __str__(self) -> str:
        if self._analog != '':
            return f'MX{self._analog}'
        return f'DX{self._digital}'

    def __add__(self, other):
        return str(self) + other

    def __radd__(self, other):
        return other + str(self)

class OutputID():
    """Represents an output, which can be either an analog stereo amplifier
        zone or a a digital stereo output"""
    def __init__(self):
        self._analog = ''
        self._digital = ''

    @classmethod
    def create_analog(cls, selection: int):
        """Analog stereo amplifier zone options are 1-8, inclusive"""
        instance = OutputID()
        instance._analog = selection
        return instance

    @classmethod
    def create_digital(cls, selection: str):
        """Digital stereo output options are 'a' or 'b'"""
        instance = OutputID()
        instance._digital = selection
        return instance

    @classmethod
    def create_from_status_id(cls, status_id: str):
        """Create instance from status ID string"""
        numeric_id = int(status_id)
        instance = OutputID()
        if numeric_id >= 1 and numeric_id <= 8:
            instance._analog = numeric_id
        else:
            instance._digital = 'a' if numeric_id == 9 else 'b'
        return instance

    def __str__(self) -> str:
        if self._analog != '':
            return f'Z{self._analog}'
        return f'DXO{self._digital}'
    
    def __add__(self, other):
        return str(self) + other

    def __radd__(self, other):
        return other + str(self)

class OutputStatus():
    """Represents the status of an analog zone or digital output"""
    def __init__(
        self,
        output_id: OutputID,
        name: str,
        input_id: InputID,
        is_on: bool,
        volume: int,
        is_signal_sense_on: bool
    ):
        self._output_id = output_id
        self._name = name
        self._input_id = input_id
        self._is_on = is_on
        self._volume = volume,
        self._is_signal_sense_on = is_signal_sense_on

    @property
    def output_id(self) -> OutputID:
        """Output ID"""
        return self._output_id

    @property
    def name(self) -> str:
        """Name"""
        return self._name

    @property
    def input_id(self) -> InputID:
        """Input ID"""
        return self._input_id

    @property
    def is_on(self) -> bool:
        """Power status (True for 'on', False for 'off')"""
        return self._is_on

    @property
    def volume(self) -> int:
        """Volume (0-100)"""
        return self._volume

    @property
    def is_signal_sense_on(self) -> bool:
        """Signal sense status (True for 'on', False for 'off')"""
        return self._is_signal_sense_on

class TelnetClient():
    """Represents a client for communicating with the telnet server of an
        AudioControl Director M6400/M6800."""

    def __init__(self, host):
        self._reader = None
        self._writer = None
        self._host = host

    async def async_connect(self) -> None:
        """Connects to the telnet server."""
        self._reader, self._writer = await telnetlib3.open_connection(self._host)

        # Disable echo
        #self._writer.send_iac(IAC + DONT + ECHO)
        #self._writer.send_iac(IAC + WILL + ECHO)
        #await self._writer.drain()

        # write_raw_sequence(tn, telnetlib.IAC + telnetlib.WILL + telnetlib.ECHO)

    # def _write_raw_sequence(tn, seq):
    #     sock = tn.get_socket()
    #     if sock is not None:
    #         sock.send(seq)

    async def async_disconnect(self) -> None:
        await self._writer.close()

    async def _async_send_command(self, command: str) -> str:
        """Sends given command to the server. Automatically appends
            CR to the command string."""
        self._writer.write(command + '\r')
        await self._writer.drain()

        empty_bytes = ''
        partial_result = ''
        result = ''
        while True:
            partial_result = await self._reader.read(1024)
            if partial_result == empty_bytes:
                break
            result += partial_result
            if result.endswith('\n'):
                break
        return result

    def _interpret_result(
        self,
        command: str,
        response: str,
        expect_success_code: bool
    ) -> tuple[bool, str]:
        """Parses the response for errors or successes, with results."""
        succeeded = False

        response_parts = response.split('\r', 1)

        # response should start with echo of command; anything else is unexpected
        command_echo = response_parts[0]
        if command_echo != command:
            raise Exception(f'Received unexpected response; \
                first line was not echo of command; got: {command_echo}')

        # remainder of the response is the result of the command
        result = response_parts[1]
        if result == f'xx{command}xx\r':
            # this is a "bad command" response
            raise BadCommandError(f'Received "bad command" response: xx{command}xx')
        if result == f'01{command}\r':
            # this is a "success" response
            succeeded = True
        if expect_success_code:
            return (succeeded, result)
        return (True, result)

    async def async_map_input_to_output(
        self,
        input_id: InputID,
        output_id: OutputID
    ):
        """Maps an input (analog input/digital input) to an output (analog zone/digital output)"""
        command = f'{output_id}source{input_id}'
        result = await self._async_send_command(command)
        result = self._interpret_result(command, result, True)[1]
        return result

    async def async_get_system_status_raw(self) -> str:
        """Returns full system status in raw form"""
        command = 'SYSTEMstat?'
        result = await self._async_send_command(command)
        return self._interpret_result(command, result, False)[1]

    async def async_get_system_status(self) -> OutputStatus:
        """Returns full system status"""
        raw_result = await self.async_get_system_status_raw()
        result_lines = raw_result.split('\r\n')

        # ------------------------------
        # Response format is as follows:
        # ------------------------------
        # pylint: disable=trailing-whitespace
        # ------------------------------

        # AMPLIFIER NAME: Director Matrix 6800 #3
        # GLOBAL TEMP: 111 F & Normal
        # GLOBAL VOLTAGE: 126 & Normal
        # ZONE OUTPUT PROTECT: 
        # GLOBAL PROTECTION: Normal
        # THERMAL PROTECTION: Normal
        # IP ADDRESS: 10.111.16.52
        # DATE 10/10/2022
        # TIME '17:30:08
        # 
        # ZONES, #, POWER STATE, INPUT, VOLUME, BASS, TREBLE, EQ, GROUP, TEMP, SIG. SENSE
        # Zone 1, 1, on, MX1 & 1, 100, 0, 0, Acoustic and 0, 0, 111 F/Normal, off
        # Zone 2, 2, on, MX2 & 2, 100, 0, 0, Acoustic and 0, 0, 111 F/Normal, off
        # Zone 3, 3, on, MX3 & 3, 100, 0, 0, User 3 and 5, 0, 113 F/Normal, off
        # Zone 4, 4, on, MX4 & 4, 100, 0, 0, unsaved values and -1, 0, 113 F/Normal, off
        # Zone 5, 5, on, MX5 & 5, 100, 0, 0, User 3 and 5, 0, 113 F/Normal, off
        # Zone 6, 6, on, MX6 & 6, 100, 0, 0, User 3 and 5, 0, 113 F/Normal, off
        # Zone 7, 7, on, MX7 & 7, 100, 0, 0, Party and 2, 0, 109 F/Normal, off
        # Zone 8, 8, on, MX8 & 8, 100, 0, 0, Party and 2, 0, 109 F/Normal, off
        # Digital Out A, 9, on, MX10 & 10, 100, 0, 0, unsaved values and -1, 0, 0 F/Low, off
        # Digital Out B, 10, on, MX10 & 10, 100, 0, 0, unsaved values and -1, 0, 0 F/Low, off

        # ------------------------------
        # pylint: enable=trailing-whitespace
        # ------------------------------

        # get the lines that represent the comma-separated data for each analog zone/digital output
        ret_val = []
        output_lines = result_lines[11:21]
        for result_line in output_lines:
            fields = result_line.split(', ')

            name = fields[0]

            raw_output_id = int(fields[1]) # parse int
            output_id = OutputID.create_from_status_id(raw_output_id)

            is_on = fields[2] == 'on'

            raw_input_id = fields[3]
            input_id = InputID.create_from_status_id(raw_input_id)

            volume = int(fields[4])

            #bass = int(fields[5])
            #treble = int(fields[6])
            #eq = fields[7] # parse the "Acoustic and 0" format
            #group_id = int(fields[8])
            #temperature = fields[9] # parse temp

            is_signal_sense_on = fields[10] == 'on'

            element = OutputStatus(output_id, name, input_id, is_on, volume, is_signal_sense_on)
            ret_val.append(element)

        return ret_val


class BadCommandError(Exception):
    """Signifies that an unrecognized command was sent"""