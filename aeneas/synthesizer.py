#!/usr/bin/env python
# coding=utf-8

# aeneas is a Python/C library and a set of tools
# to automagically synchronize audio and text (aka forced alignment)
#
# Copyright (C) 2012-2013, Alberto Pettarin (www.albertopettarin.it)
# Copyright (C) 2013-2015, ReadBeyond Srl   (www.readbeyond.it)
# Copyright (C) 2015-2016, Alberto Pettarin (www.albertopettarin.it)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
This module contains the following classes:

* :class:`~aeneas.synthesizer.Synthesizer`,
  for synthesizing text fragments into an audio file,
  along with the corresponding time anchors.

.. warning:: This module might be refactored in a future version
"""

from __future__ import absolute_import
from __future__ import print_function
from aeneas.espeakwrapper import ESPEAKWrapper
from aeneas.festivalwrapper import FESTIVALWrapper
from aeneas.logger import Loggable
from aeneas.nuancettsapiwrapper import NuanceTTSAPIWrapper
from aeneas.runtimeconfiguration import RuntimeConfiguration
from aeneas.textfile import TextFile
import aeneas.globalfunctions as gf


class Synthesizer(Loggable):
    """
    A class to synthesize text fragments into
    an audio file,
    along with the corresponding time anchors.

    :param rconf: a runtime configuration
    :type  rconf: :class:`~aeneas.runtimeconfiguration.RuntimeConfiguration`
    :param logger: the logger object
    :type  logger: :class:`~aeneas.logger.Logger`
    :raises: OSError: if a custom TTS engine is requested but it cannot be loaded
    :raises: ImportError: if the Nuance TTS API wrapper is requested but
                          the``requests`` module is not installed
    """

    CUSTOM = "custom"
    """ Select custom TTS engine wrapper """

    ESPEAK = "espeak"
    """ Select eSpeak wrapper """

    FESTIVAL = "festival"
    """ Select Festival wrapper """

    NUANCETTSAPI = "nuancettsapi"
    """ Select Nuance TTS API wrapper """

    ALLOWED_VALUES = [CUSTOM, ESPEAK, FESTIVAL, NUANCETTSAPI]
    """ List of all the allowed values """

    TAG = u"Synthesizer"

    def __init__(self, rconf=None, logger=None):
        super(Synthesizer, self).__init__(rconf=rconf, logger=logger)
        self.tts_engine = None
        self._select_tts_engine()

    def _select_tts_engine(self):
        """
        Select the TTS engine to be used by looking at the rconf object.
        """
        self.log(u"Selecting TTS engine...")
        if self.rconf[RuntimeConfiguration.TTS] == self.CUSTOM:
            self.log(u"TTS engine: custom")
            tts_path = self.rconf[RuntimeConfiguration.TTS_PATH]
            if not gf.file_can_be_read(tts_path):
                self.log_exc(u"Cannot read tts_path", None, True, OSError)
            try:
                import imp
                self.log([u"Loading CustomTTSWrapper module from '%s'...", tts_path])
                imp.load_source("CustomTTSWrapperModule", tts_path)
                self.log([u"Loading CustomTTSWrapper module from '%s'... done", tts_path])
                self.log(u"Importing CustomTTSWrapper...")
                from CustomTTSWrapperModule import CustomTTSWrapper
                self.log(u"Importing CustomTTSWrapper... done")
                self.log(u"Creating CustomTTSWrapper instance...")
                self.tts_engine = CustomTTSWrapper(rconf=self.rconf, logger=self.logger)
                self.log(u"Creating CustomTTSWrapper instance... done")
            except Exception as exc:
                self.log_exc(u"Unable to load custom TTS wrapper", exc, True, OSError)
        elif self.rconf[RuntimeConfiguration.TTS] == self.FESTIVAL:
            self.log(u"TTS engine: Festival")
            self.tts_engine = FESTIVALWrapper(rconf=self.rconf, logger=self.logger)
        elif self.rconf[RuntimeConfiguration.TTS] == self.NUANCETTSAPI:
            try:
                import requests
            except ImportError as exc:
                self.log_exc(u"Unable to import requests for Nuance TTS API wrapper", exc, True, ImportError)
            self.log(u"TTS engine: Nuance TTS API")
            self.tts_engine = NuanceTTSAPIWrapper(rconf=self.rconf, logger=self.logger)
        else:
            self.log(u"TTS engine: eSpeak")
            self.tts_engine = ESPEAKWrapper(rconf=self.rconf, logger=self.logger)
        self.log(u"Selecting TTS engine... done")

    def output_is_mono_wave(self):
        """
        Return ``True`` if the TTS engine
        outputs a PCM16 mono WAVE file.

        This information can be used to avoid
        converting the audio file output by the TTS engine.

        :rtype: bool
        """
        if self.tts_engine is not None:
            return self.tts_engine.OUTPUT_MONO_WAVE
        return False

    def synthesize(
            self,
            text_file,
            audio_file_path,
            quit_after=None,
            backwards=False
    ):
        """
        Synthesize the text contained in the given fragment list
        into a ``wav`` file.

        Return a tuple ``(anchors, total_time, num_chars)``.

        :param text_file: the text file to be synthesized
        :type  text_file: :class:`~aeneas.textfile.TextFile`
        :param string audio_file_path: the path to the output audio file
        :param float quit_after: stop synthesizing as soon as
                                 reaching this many seconds
        :param bool backwards: if ``True``, synthesizing from the end of the text file
        :rtype: tuple
        :raises: TypeError: if ``text_file`` is ``None`` or not an instance of ``TextFile``
        :raises: OSError: if ``audio_file_path`` cannot be written
        :raises: OSError: if ``tts=custom`` in the RuntimeConfiguration and ``tts_path`` cannot be read
        """
        if text_file is None:
            self.log_exc(u"text_file is None", None, True, TypeError)
        if not isinstance(text_file, TextFile):
            self.log_exc(u"text_file is not an instance of TextFile", None, True, TypeError)
        if not gf.file_can_be_written(audio_file_path):
            self.log_exc(u"Audio file path '%s' cannot be written" % (audio_file_path), None, True, OSError)
        if self.tts_engine is None:
            self.log_exc(u"Cannot select the TTS engine", None, True, ValueError)

        # synthesize
        self.log(u"Synthesizing text...")
        result = self.tts_engine.synthesize_multiple(
            text_file=text_file,
            output_file_path=audio_file_path,
            quit_after=quit_after,
            backwards=backwards
        )
        self.log(u"Synthesizing text... done")

        # check that the output file has been written
        if not gf.file_exists(audio_file_path):
            self.log_exc(u"Audio file path '%s' cannot be read" % (audio_file_path), None, True, OSError)

        return result
