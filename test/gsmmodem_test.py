#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


import unittest
import pygsm

from mock.device import MockDevice, MockSenderDevice


class TestModem(unittest.TestCase):
    
    def testMaxMessageArgs(self):
        # this device is much more complicated than
        # most, so is tucked away in mock.device
        device = MockSenderDevice()
        gsmPDU = pygsm.GsmModem(device=device, mode="PDU")
        gsmTEXT = pygsm.GsmModem(device=device, mode="TEXT")

        for gsm in (gsmPDU, gsmTEXT):
            # test with no max_message arg
            gsm.send_sms("1234", "Test Message")
            self.assertEqual(device.sent_messages[0]["recipient"], "21")
            self.assertEqual(device.sent_messages[0]["text"], "00110004A821430000AA0CD4F29C0E6A96E7F3F0B90C")
            
            # test with reasonable max_message arg, should have no impact
            gsm.send_sms("1234", "Test Message", max_messages = 20)
            self.assertEqual(device.sent_messages[0]["recipient"], "21")
            self.assertEqual(device.sent_messages[0]["text"], "00110004A821430000AA0CD4F29C0E6A96E7F3F0B90C")
            
            # test with max_message = 0, should internally set to 1 with no problems
            gsm.send_sms("1234", "Test Message", -1)
            self.assertEqual(device.sent_messages[0]["recipient"], "21")
            self.assertEqual(device.sent_messages[0]["text"], "00110004A821430000AA0CD4F29C0E6A96E7F3F0B90C")
            
            # test with max_message > 255, should internally force to 255
            gsm.send_sms("1234", "Test Message", 1024)
            self.assertEqual(device.sent_messages[0]["recipient"], "21")
            self.assertEqual(device.sent_messages[0]["text"], "00110004A821430000AA0CD4F29C0E6A96E7F3F0B90C")
            
        # test with max_message = 1 and message too long to fit
        # should throw a value exception
        #
        # ONLY SUPPORTED IN PDU MODE, so run on PDU configured gsmmodem only
        msg="""
        0123456789012345678901234567890123456789012345678901234567890123456789
        0123456789012345678901234567890123456789012345678901234567890123456789
        0123456789012345678901234567890123456789012345678901234567890123456789
        0123456789012345678901234567890123456789012345678901234567890123456789
        0123456789012345678901234567890123456789012345678901234567890123456789
        0123456789012345678901234567890123456789012345678901234567890123456789
        0123456789012345678901234567890123456789012345678901234567890123456789
        """
        try:
            gsmPDU.send_sms("1234", msg, max_messages=1)
        except ValueError:
            print "ValueError caught"
        else:
            # Should have thrown an error!
            self.assertTrue(False) # SMS too big should throw ValueError

    def testSendSmsPDUMode(self):
        """Checks that the GsmModem in PDU mode accepts outgoing SMS,
           when the text is within ASCII chars 22 - 126."""

        # this device is much more complicated than
        # most, so is tucked away in mock.device
        device = MockSenderDevice()
        gsm = pygsm.GsmModem(device=device, mode="PDU")

        # send an sms, and check that it arrived safely
        gsm.send_sms("1234", "Test Message")
        self.assertEqual(device.sent_messages[0]["recipient"], "21")
        self.assertEqual(device.sent_messages[0]["text"], "00110004A821430000AA0CD4F29C0E6A96E7F3F0B90C")

    def testSendSmsTextMode(self):
        """Checks that the GsmModem in TEXT mode accepts outgoing SMS,
           when the text is within ASCII chars 22 - 126."""

        # this device is much more complicated than
        # most, so is tucked away in mock.device
        device = MockSenderDevice()
        gsm = pygsm.GsmModem(device=device, mode="TEXT")

        # send an sms, and check that it arrived safely
        gsm.send_sms("1234", "Test Message")
        self.assertEqual(device.sent_messages[0]["recipient"], "1234")
        self.assertEqual(device.sent_messages[0]["text"], "Test Message")

    def testRetryCommands(self):
        """Checks that the GsmModem automatically retries
           commands that fail with a CMS 515 error, and does
           not retry those that fail with other errors."""
        
        class MockBusyDevice(MockDevice):
            def __init__(self):
                MockDevice.__init__(self)
                self.last_cmd = None
                self.retried = []
            
            # this command is special (and totally made up)
            # it does not return 515 errors like the others
            def at_test(self, one):
                return True
            
            def process(self, cmd):
                
                # if this is the first time we've seen
                # this command, return a BUSY error to
                # (hopefully) prompt a retry
                if self.last_cmd != cmd:
                    self._output("+CMS ERROR: 515")
                    self.last_cmd = cmd
                    return None
                
                # the second time, note that this command was
                # retried, then fail. kind of anticlimatic
                self.retried.append(cmd)
                return False
        
        # boot the modem, and make sure that
        # some commands were retried (i won't
        # check _exactly_ how many, since we
        # change the boot sequence often)
        device = MockBusyDevice()
        n = len(device.retried)
        gsm = pygsm.GsmModem(device=device)
        self.assert_(len(device.retried) > n)
        
        # try the special AT+TEST command, which doesn't
        # fail - the number of retries shouldn't change
        n = len(device.retried)
        gsm.command("AT+TEST=1")
        self.assertEqual(len(device.retried), n)
        


    def testEchoOff(self):
        """Checks that GsmModem disables echo at some point
           during boot, to simplify logging and processing."""

        class MockEchoDevice(MockDevice):
            def process(self, cmd):
                # raise and error for any
                # cmd other than ECHO OFF
                if cmd != "ATE0":
                    return False
                
                self.echo = False
                return True

        device = MockEchoDevice()
        gsm = pygsm.GsmModem(device=device)
        self.assertEqual(device.echo, False)

    def testModemSniffing(self):
        class MockSiemensTC35i(MockDevice):
            def __init__(self):
                MockDevice.__init__(self)
                MockDevice.model = "TC35i"
                MockDevice.wind_called = False
                MockDevice.cgmm_called = False

            def at_cgmm(self): 
                self._output(self.model)
                self.cgmm_called = True
                return True
            
            def at_wind(self, switch):
                self.wind_called = True
                return False

            def at_cnmi(self, settings):
                self.cnmi_settings = settings
                return True

        device = MockSiemensTC35i()
        gsm = pygsm.GsmModem(device=device)
        self.assertEqual(device.cnmi_settings, "2,2,0,0,1")
        self.assertEqual(device.cgmm_called, True)
        self.assertEqual(device.wind_called, False)

    def testUsefulErrors(self):
        """Checks that GsmModem attempts to enable useful errors
           during boot, to make the errors raised useful to humans.
           Many modems don't support this, but it's very useful."""

        class MockUsefulErrorsDevice(MockDevice):
            def __init__(self):
                MockDevice.__init__(self)
                self.useful_errors = False

            def at_cmee(self, error_mode):
                if error_mode == "1":
                    self.useful_errors = True 
                    return True

                elif error_mode == "0":
                    self.useful_errors = False
                    return True

                # invalid mode
                return False

        device = MockUsefulErrorsDevice()
        gsm = pygsm.GsmModem(device=device)
        self.assertEqual(device.useful_errors, True)


if __name__ == "__main__":
    unittest.main()
