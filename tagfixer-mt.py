#!/usr/bin/python

# -*- coding: utf-8 -*-

import os, subprocess, urllib, json, sys
import mutagen, argparse
import threading, Queue, time


class TagFixer:
    def __init__(self):
        self.API_KEY = "YOUR_API_KEY"
        self.API_URL = "http://ws.audioscrobbler.com/2.0/"
        self.MIN_RANK = 0.0
        self.files = []
        self.IMG_SIZES = ["extralarge", "large", "medium", "small"]
        self.BAD_IMAGES = ["noimage"]
        self.devnull = open('/dev/null', 'w')

        self.ERROR = ["OK",
                      "Error while getting fingerprint data",
                      "No data in response",
                      "No suitable track/No track data",
                      "MBID not found",
                      "Error while renaming file"]


    def fixFile(self, path):
        output = None
        code = 0
        try:
            output = subprocess.check_output(["./lastfm-fpclient-json", path], stderr=self.devnull)
        except subprocess.CalledProcessError as e:
            code = e.returncode
        if (code != 0):
            return 1

        output = output.decode("utf-8")
        try:
            jsn = json.loads(output)
        except:
            return 2
            
        tracks = None
        try:
            tracks = jsn["tracks"]["track"]
        except:
            return 2

        mbids = []
        for track in tracks:
            try:
                mbids.append(track["mbid"])
            except:
                pass

        if (len(mbids) == 0):
            return 4

        album = None
        trackName = None
        artistName = None
        images = []
        imgData = None
        imageData = None
        imageType = None

        for mbid in mbids:
            if (trackName and artistName and album and imgData):
                break
            url = self.API_URL + "?method=track.getInfo&api_key=" + self.API_KEY + "&mbid=" + mbid + "&format=json"
            info = urllib.urlopen(url).read().decode("utf-8")
            js = json.loads(info)
            if (not js.get("track")):
                continue
            if (not album):
                try:
                    album = js["track"]["album"]["title"].title()
                except:
                    pass
            if (not trackName):
                try:
                    trackName = js["track"]["name"].title()
                except:
                    pass
            if (not artistName):
                try:
                    artistName = js["track"]["artist"]["name"].title()
                except:
                   pass

            if (not imgData):
                try:
                    images = js["track"]["album"]["image"]
                except:
                    pass

                if (len(images) > 0):
                    imgUrl = None
                    url = None
                    found = False
                    for sz in self.IMG_SIZES:
                        if found:
                            break
                        for img in images:
                            if found:
                                break
                            if (img["size"] == sz and not found):
                                url = img["#text"]
                                hasForbidden = False
                                for forb in self.BAD_IMAGES:
                                    if (url.count(forb) > 0):
                                        hasForbidden = True
                                if (not hasForbidden):
                                    imgUrl = url
                                    found = True

                    if found:
                        imgData = urllib.urlopen(imgUrl).read()
                        if (imgUrl.endswith('.png')):
                            imgType = 'image/png'
                        elif (imgUrl.endswith('.jpg')):
                            imgType = 'image/jpg'
                        elif (imgUrl.endswith('.jpeg')):
                            imgType = 'image/jpeg'
                        elif (imgUrl.endswith('.gif')):
                            imgType = 'image/gif'
                        else:
                            open('extensions.txt', 'w+').write(imgUrl + "\n")

        audio = mutagen.File(path)
        audio['TALB'] = mutagen.id3.TALB(3, album if album else "")
        audio['TPE1'] = mutagen.id3.TPE1(3, artistName if artistName else "")
        audio['TIT2'] = mutagen.id3.TIT2(3, trackName if trackName else "")

        if (imgData):
            pic = mutagen.id3.APIC(3, imgType, 3, 'Front cover', imgData)
            audio.tags.add(pic)

        audio.save()

        prefix = path[:path.rfind('/')+1]

        try:
            if (artistName and trackName):
                os.rename(path, prefix + artistName + " - " + trackName + ".mp3")
        except:
            return 5

        return 0


    def fixDir(self, path):
        del self.files[:]
        for dirname, dirnames, filenames in os.walk(path):
            for filename in filenames:
                mFile = os.path.join(dirname, filename)
                if (mFile.endswith(".mp3")):
                    self.files.append(mFile)
        sys.stdout.write("Found {} files\n".format(len(self.files)))

        fixed = 0
        failed = 0
        for f in self.files:
            status = self.fixFile(f)
            if (status == 0):
                fixed += 1
            else:
                failed += 1
            sys.stdout.write("\r{}/{} processed | {}: success, {}: failed".format(fixed + failed, len(self.files), fixed, failed))
            sys.stdout.flush()
        print ''


global fixer
global fixedCnt, filesCnt, goodFixes, workQueue



def threadedFix():
    global workQueue, fixed, fixedCnt, goodFixes
    while True:
        filename = workQueue.get()
        if not filename:
            break
        result = fixer.fixFile(filename)
        fixedCnt += 1
        if (result == 0):
            goodFixes += 1
        

def getVars():
    global fixedCnt, filesCnt, goodFixes
    return (fixedCnt, filesCnt, goodFixes, )


def showProgress():
    while True:
        fixedCnt, filesCnt, goodFixes = getVars()
        sys.stdout.write(" " * 50 + "\rFixed {}/{} ({} ok, {} failed)".format(fixedCnt, filesCnt, goodFixes, fixedCnt - goodFixes))
        sys.stdout.flush()
        if (fixedCnt >= filesCnt):
            break
        time.sleep(0.25)
    sys.stdout.write('\n')



if __name__ == "__main__":
    
    NUM_THREADS = 5
    
    global fixer, fixedCnt, filesCnt, goodFixes, workQueue
    fixedCnt = 0
    filesCnt = 0
    goodFixes = 0
    fixer = TagFixer()

    parser = argparse.ArgumentParser()
    parser.add_argument("dir", help="path to directory to be fixed")
    args = parser.parse_args()
    path = args.dir

    if (path.endswith('.mp3')):
        fixer.fixFile(path)
        exit(0)

    workQueue = Queue.Queue()
    filesCnt = 0
    for dirname, dirnames, filenames in os.walk(path):
        for filename in filenames:
            mFile = os.path.join(dirname, filename)
            if (mFile.endswith(".mp3")):
                workQueue.put(mFile)
                filesCnt += 1

    for i in range(NUM_THREADS):
        workQueue.put(None)
        
    sys.stdout.write("Found {} files\n".format(filesCnt))
    
    progress = threading.Thread(target=showProgress)
    progress.start()

    threads = []

    for i in range(NUM_THREADS):
        thread = threading.Thread(target=threadedFix)
        threads.append(thread)

    for i in threads:
        i.start()
        
    for i in threads:
        i.join()

    progress.join()
