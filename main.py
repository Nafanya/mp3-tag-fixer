# -*- coding: utf-8 -*-

import os, subprocess, urllib, json, sys
import mutagen, multiprocessing, argparse


class TagFixer:
    def __init__(self):
        self.CORES = multiprocessing.cpu_count()
        self.API_KEY = "YOUR_API_KEY@last.fm"
        self.API_URL = "http://ws.audioscrobbler.com/2.0/"
        self.MIN_RANK = 0.0
        self.files = []
        self.IMG_SIZES = ["extralarge", "large", "medium", "small"]
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
        jsn = json.loads(output)

        tracks = None
        try:
            tracks = jsn["tracks"]["track"]
        except:
            return 2

        ind = -1
        i = 0
        for track in tracks:
            try:
                rank = float(track["@attr"]["rank"])
            except:
                break
            if (rank > self.MIN_RANK):
                ind = i
                break
            i += 1

        if (ind == -1):
            return 3

        mbid = tracks[i]["mbid"]
        if (mbid == ""):
            #print path
            return 4
        #print mbid

        url = self.API_URL + "?method=track.getInfo&api_key=" + self.API_KEY + "&mbid=" + mbid + "&format=json"
        info = urllib.urlopen(url).read().decode("utf-8")

        js = json.loads(info)
        if (not js.get("track")):
            return 3

        album = None
        trackName = None
        artistName = None
        images = []

        try:
            album = js["track"]["album"]["title"].title()
        except:
            pass#print 'No album info'

        try:
            trackName = js["track"]["name"].title()
        except:
            pass#print 'No track name info'

        try:
            artistName = js["track"]["artist"]["name"].title()
        except:
           pass#print 'No artist info'

        try:
            images = js["track"]["album"]["image"]
        except:
            pass#print 'No images'

        imgUrl = None
        cont = True
        for sz in self.IMG_SIZES:
            if not cont:
                break
            for img in images:
                if (img["size"] == sz):
                    imgUrl = img["#text"]
                    cont = False
                    break

        imgData = None
        imgType = None
        if (imgUrl):
            imgData = urllib.urlopen(imgUrl).read()
            if (imgUrl.endswith('.png')):
                imgType = 'image/png'
            elif (imgUrl.endswith('.jpg')):
                imgType = 'image/jpg'
            elif (imgUrl.endswith('.jpeg')):
                imgType = 'image/jpeg'
            else:
                open('extensions.txt', 'r+').write(imgUrl)

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
                #print "\n", self.ERROR[status]
            sys.stdout.write("\r{}/{} processed | {}: success, {}: failed".format(fixed + failed, len(self.files), fixed, failed))
            sys.stdout.flush()
        print ''

if __name__ == "__main__":
    fixer = TagFixer()
    parser = argparse.ArgumentParser()
    parser.add_argument("dir", help="path to directory to be fixed")
    args = parser.parse_args()
    path = args.dir

    if (path.endswith('.mp3')):
        fixer.fixFile(path)
    else:
        fixer.fixDir(path)

    #fixer.fixFile("/home/nafanya/Music/lana.mp3")
    #fixer.fixDir("/home/nafanya/Music/test")
    #fixer.fixFile("/home/nafanya/programming/python/tagfixer.mp3")
    #fixer.fixFile("/home/nafanya/Music/Epic/Two steps from hell - To glory.mp3") #no image
    #fixer.fixFile(u"/home/nafanya/Music/test/Inna - Deja Vu.mp3")

