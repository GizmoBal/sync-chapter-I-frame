#!/usr/bin/env python3

import os
import sys
import re
import subprocess
import argparse
import math
import datetime
from vapoursynth import core
from pathlib import Path
from colorama import init as colorama_init
from colorama import Fore
from colorama import Style

def getDeltaTime(string):
    hours = int(re.search("^([0-9]+):",string).group(1))
    minutes = int(re.search("^[0-9]+:([0-9]+)",string).group(1))
    remain = re.search("^[0-9]+:[0-9]+:([0-9.]+)",string).group(1)
    seconds = math.floor(float(remain))
    microseconds = int((float(remain)-float(seconds))*1000000)
    duration = datetime.timedelta(hours=hours,minutes=minutes,seconds=seconds,microseconds=microseconds)
    return duration

colorama_init()

parser = argparse.ArgumentParser( \
    description='This script change timecodes in a xml/txt chapter file to match the nearest I-frame of a video file (or a P-frame if the nearest I-frame is too far)')

parser.add_argument('chapter', type=str, help='Absolute or relative path to xml/txt chapter file')
parser.add_argument('video', type=str, help='Absolute or relative path to mkv/hevc/265/avc/264 video file')
parser.add_argument('-p', '--pframe', type=int, help='Maximal admissible distance to nearest I-frame')

args = parser.parse_args()

chapterFile = os.path.abspath(args.chapter)
videoFile = os.path.abspath(args.video)
pframe = args.pframe

if not os.path.exists(chapterFile):
    sys.exit(Fore.RED + "Chapter file not found." + Style.RESET_ALL)
if not os.path.exists(videoFile):
    sys.exit(Fore.RED + "Video file not found." + Style.RESET_ALL)
if pframe == None:
    pframe = 10000

chapExt = os.path.splitext(chapterFile)[1]

# Strip all <ChapterTimeEnd>
# subprocess.run("sed -i '' '/TimeEnd/d' " + chapterFile,shell=True)

if chapExt == '.xml':
    numberChapter = int(subprocess.getoutput("grep 'ChapterTimeStart' " + chapterFile + " | wc -l"))
elif chapExt =='.txt':
    numberChapter = numberChapter = int(subprocess.getoutput("cat " + chapterFile + " | wc -l"))
    numberChapter = int(numberChapter/2)
else:
    sys.exit(Fore.RED + "Wrong chapter file." + Style.RESET_ALL)
if numberChapter < 1:
    sys.exit(Fore.RED + "Wrong chapter file." + Style.RESET_ALL)

frameRateLine = str(subprocess.getoutput("mediainfo " + videoFile + " | head -n 10 | grep 'Frame rate'"))
if len(frameRateLine) > 0:
    frameRate = re.search("[0-9][0-9.]*",frameRateLine).group()
else:
    sys.exit(Fore.RED + "Wrong video file." + Style.RESET_ALL)

if float(frameRate) < 5.0 or float(frameRate) > 100.0:
    sys.exit(Fore.RED + "Wrong frame rate." + Style.RESET_ALL)

video = core.ffms2.Source(str(videoFile))

# increment = datetime.timedelta(microseconds=1000000*round(1/float(frameRate),6))

print('')
print(f"{Fore.BLUE}{chapterFile}{Style.RESET_ALL} has {Fore.BLUE}{numberChapter:d}{Style.RESET_ALL} chapters.")
print(f"{Fore.BLUE}{videoFile}{Style.RESET_ALL} has frame rate {Fore.BLUE}{frameRate}{Style.RESET_ALL} fps.")

chapter = open(chapterFile, 'r')
chapterText = chapter.read()
chapter.close()

if chapExt == '.xml':
    timecodeOrig = re.findall("<ChapterTimeStart>([0-9.:;]*)</ChapterTimeStart>",chapterText)
else:
    timecodeOrig = re.findall("([0-9]+:[0-9]+:[0-9]+[0-9.]*)",chapterText)


testInit = int(getDeltaTime(timecodeOrig[0]).total_seconds())
if testInit != 0:
    sys.exit(Fore.RED + "First chapter does not start at the beginning." + Style.RESET_ALL)
if int(round(float(frameRate)*getDeltaTime(timecodeOrig[int(numberChapter-1)]).total_seconds(),0)) > video.num_frames:
    sys.exit(Fore.RED + "Chapter file and video file are inconsistent." + Style.RESET_ALL)

timecodeSynced = []
timecodeSynced.append(timecodeOrig[0])

print('')
frameNumber = int(round(float(frameRate)*getDeltaTime(timecodeOrig[0]).total_seconds(),0))
typeFrame = video.get_frame(frameNumber).props['_PictType']
print(f"Chapter {Fore.BLUE}1{Style.RESET_ALL} shifted by {Fore.BLUE}0{Style.RESET_ALL} frame(s) to get {Fore.BLUE}{typeFrame}{Style.RESET_ALL}-frame.")
for i in range(1,len(timecodeOrig)):
    frameNumber = int(round(float(frameRate)*getDeltaTime(timecodeOrig[i]).total_seconds(),0))
    typeFrame = video.get_frame(frameNumber).props['_PictType']
    if typeFrame != 'I':
        matchPlus = False
        matchMoins = False
        deltaFrame = 0
        while matchPlus == False and matchMoins == False and deltaFrame <= pframe:
            deltaFrame += 1
            typeFramePlus = video.get_frame(frameNumber+deltaFrame).props['_PictType']
            typeFrameMoins = video.get_frame(frameNumber-deltaFrame).props['_PictType']
            if typeFramePlus == 'I':
                matchPlus = True
            if typeFrameMoins == 'I':
                matchMoins = True
        if matchPlus == True:
            newFrameNumber = frameNumber + deltaFrame
            finalTypeFrame = 'I'
        elif matchMoins == True:
            newFrameNumber = frameNumber - deltaFrame
            finalTypeFrame = 'I'
        else:
            finalTypeFrame = 'P'
            matchPlus = False
            matchMoins = False
            deltaFrame = 0
            while matchPlus == False and matchMoins == False:
                deltaFrame += 1
                typeFramePlus = video.get_frame(frameNumber+deltaFrame).props['_PictType']
                typeFrameMoins = video.get_frame(frameNumber-deltaFrame).props['_PictType']
                if typeFramePlus == 'P':
                    matchPlus = True
                if typeFrameMoins == 'P':
                    matchMoins = True
            if matchPlus == True:
                newFrameNumber = frameNumber + deltaFrame
            elif matchMoins == True:
                newFrameNumber = frameNumber - deltaFrame
    else:
        finalTypeFrame = 'I'
        newFrameNumber = frameNumber
    chaptIndex = i + 1
    deltaFrame = newFrameNumber - frameNumber
    print(f"Chapter {Fore.BLUE}{chaptIndex}{Style.RESET_ALL} shifted by {Fore.BLUE}{deltaFrame}{Style.RESET_ALL} frame(s) to get {Fore.BLUE}{finalTypeFrame}{Style.RESET_ALL}-frame.")
    total_seconds = round(newFrameNumber/float(frameRate),6)
    hours = int(math.floor(total_seconds/3600))
    minutes = int(math.floor((total_seconds-hours*3600)/60))
    seconds = int(math.floor(total_seconds-hours*3600-minutes*60))
    microseconds = int((total_seconds-hours*3600-minutes*60-seconds)*1000000)
    if chapExt == '.xml':
        newTimeCode = str(hours).zfill(2) + ":" + str(minutes).zfill(2) + ":" + str(seconds).zfill(2) + "." + str(microseconds).zfill(6) + "000"
    else:
        newTimeCode = str(hours).zfill(2) + ":" + str(minutes).zfill(2) + ":" + str(seconds).zfill(2) + "." + str(int(round(microseconds/1000))).zfill(3)
    timecodeSynced.append(newTimeCode)

origChapterFile = Path(chapterFile)
if chapExt == '.xml':
    syncedChapterFile = Path('sync.I.frames.chapter.xml')
else:
    syncedChapterFile = Path('sync.I.frames.chapter.txt')
syncedChapterFile.write_text(origChapterFile.read_text())
for i in range(len(timecodeOrig)):
    origString = str(timecodeOrig[i])
    newString = str(timecodeSynced[i])
    syncedChapterFile.write_text(syncedChapterFile.read_text().replace(origString,newString))

fullSyncedChapterFile = os.path.abspath(syncedChapterFile)
print('')
print(f"Chapter time codes updated in {Fore.BLUE}{fullSyncedChapterFile}{Style.RESET_ALL}!")

# print('')
# print(timecodeOrig)
# print(timecodeSynced)
