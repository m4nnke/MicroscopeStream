try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None  # Allow import on non-RPi systems for dev/testing

class LightingController:
    """
    Controls an LED via PWM on a specified GPIO pin (default: 18) at a given frequency (default: 500Hz).
    Used for microscope illumination control.
    In this circuit, duty_cycle=0 means LED fully ON, duty_cycle=100 means LED fully OFF.
    """
    def __init__(self, pin=18, frequency=500):
        self.pin = pin
        self.frequency = frequency
        self.is_on = False
        self._pwm = None
        self._initialized = False
        if GPIO:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT)
            self._pwm = GPIO.PWM(self.pin, self.frequency)
            self._pwm.start(100)  # Start with LED OFF
            self._initialized = True

    def turn_on(self, duty_cycle=0):
        if self._initialized and self._pwm:
            self._pwm.ChangeDutyCycle(duty_cycle)  # 0 = fully ON
            self.is_on = True

    def turn_off(self):
        if self._initialized and self._pwm:
            self._pwm.ChangeDutyCycle(100)  # 100 = fully OFF
            self.is_on = False

    def cleanup(self):
        if self._initialized and self._pwm:
            try:
                self._pwm.stop()
            except Exception:
                pass
            try:
                GPIO.cleanup(self.pin)
            except Exception:
                pass
            self._pwm = None
            self._initialized = False