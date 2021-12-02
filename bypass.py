import hcaptcha
import cv2
import numpy as np
import cvlib as cv
import io
import subprocess, time

def recognize(tile, word, ch):
    img = tile.get_image(raw=False)
    with io.BytesIO() as buf:
        img.save(buf, 'jpeg')
        image_bytes = buf.getvalue()
    nparr = np.frombuffer(image_bytes, np.uint8)
    im = cv2.imdecode(nparr, flags=1)
    objects = cv.detect_common_objects(im, confidence=0.5, nms_thresh=1, enable_gpu=False)[1]
    if word in objects: ch.answer(tile)

def bypass(sitekey, host, proxy):
    while True:
        try:
            ch = hcaptcha.Challenge(site_key=sitekey, site_url=host, timeout=5)
            if ch.token: return ch.token
            word = str(ch.question["en"]).replace("Please click each image containing an ", "").replace("Please click each image containing a ", "")
            if word == "motorbus": word = "bus"
            for tile in ch: recognize(tile, word, ch)
            e = ch.submit()
            return e
        except Exception as e:
            if e == "Challenge creation request was rejected.":
                time.sleep(5)
            print(e)
            pass

if __name__ == "__main__":
    bypass('f5561ba9-8f1e-40ca-9b5b-a0b3f719ef34', "https://discord.com/register", "donerbackerspeedproxies:iKDDHwo4hN3SpD50_country-UnitedStates@p.speedproxies.net:31112")
