# Qt5 imports
import PyQt5.uic
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QObject, pyqtSignal, Qt

Ui_Trigger, _ = PyQt5.uic.loadUiType("triggerconfig.ui")


class TriggerConfig(QtWidgets.QWidget):
    """Provide the UI inside the Triggering tab.

    Most of the UI is copied from MATTER, but the Python implementation in this
    class is new."""

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.ui = Ui_Trigger()
        self.ui.setupUi(self)
        self.ui.recordLengthSpinBox.editingFinished.connect(self.sendRecordLengthsToServer)
        self.ui.pretrigLengthSpinBox.editingFinished.connect(self.sendRecordLengthsToServer)
        self.ui.pretrigPercentSpinBox.editingFinished.connect(self.sendRecordLengthsToServer)
        self.ui.channelsChosenEdit.textChanged.connect(self.channelListTextChanged)
        self.trigger_state = {}
        self.chosenChannels = []

    def handleTriggerMessage(self, dicts):
        """Handle the trigger state message (in list-of-dicts form)"""
        for d in dicts:
            for ch in d["ChanNumbers"]:
                self.trigger_state[ch] = d
        self.updateTriggerGUIElements()

    def channelChooserChanged(self):
        """The channel selector menu was activated: update the edit box"""
        cctext = self.ui.channelChooserBox.currentText()
        if cctext.startswith("All"):
            allprefixes = [self.chanbyprefix(p) for p in self.channel_prefixes]
            allprefixes.sort()
            result = "\n".join(allprefixes)
        elif cctext.startswith("user"):
            return
        else:
            prefix = cctext.split()[0].lower()
            if prefix == "fb":
                prefix = "chan"
            result = self.chanbyprefix(prefix)
        self.ui.channelsChosenEdit.setPlainText(result)

    def chanbyprefix(self, prefix):
        """Return a string listing all channels for the given prefix"""
        cnum = ",".join([p.lstrip(prefix) for p in self.channel_names if p.startswith(prefix)])
        return "%s:%s" % (prefix, cnum)

    def channelListTextChanged(self):
        """The channel selector text edit box changed."""
        self.parseChannelText()
        self.updateTriggerGUIElements()

    def parseChannelText(self):
        """Parse the text in the channel selector text edit box. Set the list
        self.chosenChannels accordingly."""
        self.chosenChannels = []
        chantext = self.ui.channelsChosenEdit.toPlainText()
        print ("Trying to update the channel information")
        chantext = chantext.replace("\t", "\n").replace(";", "\n").replace(" ", "")
        lines = chantext.split()
        for line in lines:
            if ":" not in line:
                continue
            prefix, cnums = line.split(":", 1)
            if prefix not in self.channel_prefixes:
                print("Channel prefix %s not in known prefixes: %s" % (prefix, self.channel_prefixes))
                continue
            for cnum in cnums.split(","):
                name = prefix+cnum
                try:
                    idx = self.channel_names.index(name)
                    self.chosenChannels.append(idx)
                except ValueError:
                    print ("Channel %s not known" % (name))
        print "The chosen channels are ", self.chosenChannels

    def getstate(self, name):
        "Get the self.trigger_state value named name. If mutiple values, return None"
        channels = self.chosenChannels
        if len(channels) == 0:
            return None
        for ch in channels:
            if ch not in self.trigger_state:
                return None
        x = self.trigger_state[channels[0]].get(name, None)
        if x is None:
            return None
        for ch in channels[1:]:
            y = self.trigger_state[ch].get(name, None)
            if x != y:
                return None
        return x

    def alltriggerstates(self):
        """Return all unique dictionaries that are values in the self.trigger_state dict.
        There might be 100s of entries in self.trigger_state dict but only one or a few
        unique values in it."""

        # A set() might seem natural but cannot be used to store unhashable items like dicts.
        allstates = []
        for ch in self.chosenChannels:
            # This will add a trigger state to the list only if it's not already in the list.
            if ch in self.trigger_state and self.trigger_state[ch] not in allstates:
                allstates.append(self.trigger_state[ch])

        # Now we need to split states if any of allstates refers to channels both
        # in AND out of self.chosenChannels. Those dictionaries each become 2 dictionaries.
        for state in allstates:
            chans = state["ChanNumbers"]
            keep = []
            splitoff = []
            for c in chans:
                if c in self.chosenChannels:
                    keep.append(c)
                else:
                    splitoff.append(c)
            if len(splitoff) > 0:
                state["ChanNumbers"] = keep
                for c in keep:
                    self.trigger_state[c] = state
                newstate = state.copy()
                newstate["ChanNumbers"] = splitoff
                for c in splitoff:
                    self.trigger_state[c] = newstate

        return allstates

    def setstate(self, name, newvalue):
        "Set the self.trigger_state value named name to newvalue"
        for state in self.alltriggerstates():
            state[name] = newvalue
        return newvalue

    def updateTriggerGUIElements(self):
        """Given the self.chosenChannels, update the various trigger status GUI elements."""

        boxes = (
            (self.ui.autoTrigActive, "AutoTrigger"),
            (self.ui.edgeTrigActive, "EdgeTrigger"),
            (self.ui.levelTrigActive, "LevelTrigger"),
            (self.ui.noiseTrigActive, "NoiseTrigger"),
        )
        for (checkbox, name) in boxes:
            state = self.getstate(name)
            checkbox.setTristate(state is None)
            if state is not None:
                checkbox.setChecked(state)

        levelscale = edgescale = 1.0
        if self.ui.levelVoltsRaw.currentText().startswith("Volts"):
            levelscale = 1./16384.0
            edgescale = levelscale * 100  # TODO: replace 100 with samples per second
            self.ui.levelUnitsLabel.setText("Volts")
            self.ui.edgeUnitsLabel.setText("V/ms")
            self.ui.noiseUnitsLabel.setText("V/ms")
        else:
            self.ui.levelUnitsLabel.setText("raw")
            self.ui.edgeUnitsLabel.setText("raw/samp")
            self.ui.noiseUnitsLabel.setText("raw/samp")
        edits = (
            (self.ui.autoTimeEdit, "AutoDelay", 1e-6),
            (self.ui.edgeEdit, "EdgeLevel", edgescale),
            (self.ui.levelEdit, "LevelLevel", levelscale),
            # (self.ui.noiseEdit, "NoiseLevel", 1.0)
        )
        for (edit, name, scale) in edits:
            state = self.getstate(name)
            if state is None:
                edit.setText("")
                continue
            edit.setText("%f" % (state*scale))

        r = self.getstate("EdgeRising")
        f = self.getstate("EdgeFalling")
        if r and f:
            self.ui.edgeRiseFallBoth.setCurrentIndex(2)
        elif f:
            self.ui.edgeRiseFallBoth.setCurrentIndex(1)
        else:
            self.ui.edgeRiseFallBoth.setCurrentIndex(0)

    def checkedCoupleFBErr(self):
        on = self.ui.coupleFBToErrCheckBox.isChecked()
        if on:
            self.ui.coupleErrToFBCheckBox.setChecked(False)
        self.client.call("SourceControl.CoupleFBToErr", on)

    def checkedCoupleErrFB(self, on):
        on = self.ui.coupleErrToFBCheckBox.isChecked()
        if on:
            self.ui.coupleFBToErrCheckBox.setChecked(False)
        self.client.call("SourceControl.CoupleErrToFB", on)

    def handleTrigCoupling(self, msg):
        fberr = errfb = False
        if msg == 2:
            fberr = True
        elif msg == 3:
            errfb = True
        elif msg != 1:
            print "message: TRIGCOUPLING {}, but expect 1, 2 or 3".format(msg)
        self.ui.coupleFBToErrCheckBox.setChecked(fberr)
        self.ui.coupleErrToFBCheckBox.setChecked(errfb)

    def changedAutoTrigConfig(self):
        auto = self.ui.autoTrigActive.checkState()
        if not auto == Qt.PartiallyChecked:
            self.ui.autoTrigActive.setTristate(False)
            self.setstate("AutoTrigger", auto == Qt.Checked)

        delay = self.ui.autoTimeEdit.text()
        try:
            msdelay = int(float(delay)*1e6+0.5)
            self.setstate("AutoDelay", msdelay)
        except ValueError:
            pass
        for state in self.alltriggerstates():
            self.client.call("SourceControl.ConfigureTriggers", state)

    def changedEdgeTrigConfig(self):
        edge = self.ui.edgeTrigActive.checkState()
        if not edge == Qt.PartiallyChecked:
            self.ui.edgeTrigActive.setTristate(False)
            self.setstate("EdgeTrigger", edge == Qt.Checked)
        rfb = self.ui.edgeRiseFallBoth.currentText()
        if rfb.startswith("Rising"):
            self.setstate("EdgeRising", True)
            self.setstate("EdgeFalling", False)
        elif rfb.startswith("Falling"):
            self.setstate("EdgeRising", False)
            self.setstate("EdgeFalling", True)
        elif rfb.startswith("Either"):
            self.setstate("EdgeRising", True)
            self.setstate("EdgeFalling", True)

        edgeraw = self.ui.edgeEdit.text()
        edgescale = 1.0
        if self.ui.levelVoltsRaw.currentText().startswith("Volts"):
            edgescale = 1./16384.0
            # TODO: convert samples to ms
        try:
            edgeraw = int(float(edgeraw)/edgescale+0.5)
            self.setstate("EdgeLevel", edgeraw)
        except ValueError:
            pass
        for state in self.alltriggerstates():
            self.client.call("SourceControl.ConfigureTriggers", state)

    def changedLevelTrigConfig(self):
        level = self.ui.levelTrigActive.checkState()
        if not level == Qt.PartiallyChecked:
            self.ui.levelTrigActive.setTristate(False)
            self.setstate("LevelTrigger", level == Qt.Checked)
        rfb = self.ui.levelRiseFallBoth.currentText()
        if rfb.startswith("Rising"):
            self.setstate("LevelRising", True)
            self.setstate("LevelFalling", False)
        elif rfb.startswith("Falling"):
            self.setstate("LevelRising", False)
            self.setstate("LevelFalling", True)
        elif rfb.startswith("Either"):
            self.setstate("LevelRising", True)
            self.setstate("LevelFalling", True)

        levelraw = self.ui.levelEdit.text()
        levelscale = 1.0
        if self.ui.levelVoltsRaw.currentText().startswith("Volts"):
            levelscale = 1./16384.0
        try:
            levelraw = int(float(levelraw)/levelscale+0.5)
            self.setstate("LevelLevel", levelraw)
        except ValueError:
            pass
        for state in self.alltriggerstates():
            self.client.call("SourceControl.ConfigureTriggers", state)

    def changedNoiseTrigConfig(self):
        pass

    def changedLevelUnits(self):
        """Changed the edge+level units between RAW and Volts"""
        self.updateTriggerGUIElements()

    def updateRecordLengthsFromServer(self, nsamp, npre):
        samples = self.ui.recordLengthSpinBox
        if samples.value() != nsamp:
            samples.setValue(nsamp)
        pretrig = self.ui.pretrigLengthSpinBox
        if pretrig.value() != npre:
            pretrig.setValue(npre)

    def changedRecordLength(self, reclen):
        pretrig = self.ui.pretrigLengthSpinBox
        pct = self.ui.pretrigPercentSpinBox
        old_pt = pretrig.value()
        new_pt = int(0.5+reclen*pct.value()/100.0)
        if old_pt != new_pt:
            pretrig.valueChanged.disconnect()
            pretrig.setValue(new_pt)
            pretrig.valueChanged.connect(self.editedPretrigLength)

    def editedPretrigLength(self):
        samples = self.ui.recordLengthSpinBox
        pretrig = self.ui.pretrigLengthSpinBox
        pct = self.ui.pretrigPercentSpinBox
        pct.blockSignals(True)
        pct.setValue(pretrig.value()*100.0/samples.value())
        pct.blockSignals(False)

    def editedPretrigPercentage(self):
        samples = self.ui.recordLengthSpinBox
        pretrig = self.ui.pretrigLengthSpinBox
        pct = self.ui.pretrigPercentSpinBox
        pretrig.blockSignals(True)
        pretrig.setValue(int(0.5+samples.value()*pct.value()/100.0))
        pretrig.blockSignals(False)

    def sendRecordLengthsToServer(self):
        samp = self.ui.recordLengthSpinBox.value()
        presamp = self.ui.pretrigLengthSpinBox.value()
        print "Here we tell the server records are %d (%d pretrigger)" % (samp, presamp)
        self.client.call("SourceControl.ConfigurePulseLengths", {"Nsamp": samp, "Npre": presamp})
