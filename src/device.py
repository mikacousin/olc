"""Devices"""

from olc.define import App


class Device:
    """Device

    Attributes:
        channel (int): channel number
        output (int): first output used by device
        universe (int): universe
        template (Template): template used by device
        outputs (list of int): outputs used by device
    """

    def __init__(self, channel, output, universe, template):
        self.channel = channel
        self.output = output
        self.universe = universe
        for item in App().templates:
            if item.name == template:
                self.template = item
        self.outputs = []
        for out in range(output, output + self.template.footprint):
            self.outputs.append(out)


class Template:
    """Template

    Attributes:
        name (str): name
        footprint (int): number of outputs used
        manufacturer (str): manufacturer
        model_name (str): model name
        mode_name (str): mode name
        parameters (dict): dict of parameter number: Parameter
    """

    def __init__(self, name):
        self.name = name
        self.footprint = 1
        self.manufacturer = ""
        self.model_name = ""
        self.mode_name = ""
        self.parameters = {}


class Parameter:
    """Device Parameter

    Attributes:
        number (int): parameter number
        name (str): name
        default (int): default value (Home)
        highlight (int): highlight
        offset (dict): DMX offset
        range (dict): Values range (if appropriate)
        table (list): Values table (if appropriate)
    """

    def __init__(self, number):
        self.number = number
        self.name = App().parameters[number][1]
        self.default = 0
        self.highlight = 0
        self.offset = {"High Byte": 0, "Low Byte": 0, "Step": 0}
        self.range = {"Minimum": 0, "Maximum": 0, "Percent": True}
        self.table = []
