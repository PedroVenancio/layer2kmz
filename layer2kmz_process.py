# -*- coding: utf-8 -*-
"""
/***************************************************************************
 layer2kmz
                                 A QGIS plugin
 Build a kmz from a layer of spatial points, lines or polygons
                              -------------------
        begin                : 2018-02-02
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Pedro Tarroso
        email                : ptarroso@cibio.up.pt
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; version 2 of the License.               *
 *                                                                         *
 ***************************************************************************/
"""
from builtins import str, zip, range, object

from PyQt5.QtCore import QSize
from PyQt5.QtGui import QColor

import os
import tempfile
import zipfile
from .kml import kml

def conv2str(x):
    ## Converts the input to string, avoiding unicode errors
    try:
        cv = str(x)
    except UnicodeEncodeError:
        cv = x #.encode("ascii", "xmlcharrefreplace")
    return(cv)

def argb2abgr(col):
    #KML format: AlphaBGR instead of AlphaRGB
    return(col[0:2] + col[6:8] + col[4:6] + col[2:4])


class kmlprocess(object):
    def __init__(self, layer, label, folder, exports, showLbl, outFile,
                 progressbar, emitmsg):
        self.layer = layer
        self.label = label
        self.showLbl = showLbl
        self.folder = folder
        self.exports = exports
        self.styleField = None
        self.outFile = outFile
        self.tmpDir = tempfile.gettempdir()
        self.progress = progressbar
        self.emitMsg = emitmsg
        self.totalCounter = 1
        self.counter = 0

    def processLayer(self):
        lyr = self.layer
        ## Sets the total counter for updating progress
        self.totalCounter = lyr.featureCount() * 2

        lyrFields = [f.name() for f in lyr.fields()]
        expFieldInd = [lyrFields.index(f) for f in self.exports]
        featIter = lyr.getFeatures()
        fldInd = lyrFields.index(self.folder)
        lblInd = lyrFields.index(self.label)

        ## If there is a style field, save a list of style for each feature
        if self.styleField is not None:
            styles = []
            styInd = lyrFields.index(self.styleField)

        ## Process all features
        data = []
        featFolder = []
        coords = []
        labels = []

        for feature in featIter:
            self.updateProgress()

            fGeo = feature.geometry().type()

            if self.styleField is not None:
                styleFeat = conv2str(feature.attributes()[styInd])

            # Export only features that have active styles (displayed on the map)
            if (self.styleField is None or styleFeat in self.getStylesNames()):
                # note: converting everything to string!
                data.append([conv2str(feature.attributes()[i]) for i in expFieldInd])
                featFolder.append(conv2str(feature.attributes()[fldInd]))
                labels.append(conv2str(feature.attributes()[lblInd]))
                if fGeo == 0: # Point case
                    crd = tuple(feature.geometry().asPoint())
                elif fGeo == 1: # Line case
                    crd = feature.geometry().asPolyline()
                    crd = [tuple(x) for x in crd]
                elif fGeo == 2: # Polygon case
                    crd = feature.geometry().asPolygon()
                    crd = [[tuple(x) for x in y] for y in crd]
                coords.append(crd)
                if self.styleField is not None:
                    styles.append(styleFeat)
            else:
                self.totalCounter -= 1

            self.counter += 1

        self.coords = coords
        self.data = data
        self.featFolder = featFolder
        self.labels = labels
        if self.styleField is not None:
            self.featStyles = styles

    def setStyles(self):
        lyr = self.layer
        lyrGeo = lyr.geometryType()
        rnd = lyr.renderer()
        styles = []
        if rnd.type() == 'categorizedSymbol':
            styleField = rnd.classAttribute()
            self.styleField = styleField
            for cat in rnd.categories():
                name = conv2str(cat.value())
                symb = cat.symbol()
                if cat.renderState():
                    if lyrGeo == 0: ## Point case
                        imgname = "color_%s.png" % name
                        symb.exportImage(os.path.join(self.tmpDir, imgname),
                                         "png", QSize(30, 30))
                        styles.append([name, {"iconfile": imgname}])
                    elif lyrGeo == 1: ## Line case
                        color = argb2abgr("%x" % symb.color().rgba())
                        width = symb.width()
                        styles.append([name, {"color": color, "width": width}])
                    elif lyrGeo == 2: ## Polygon case
                        symbLyr = symb.symbolLayer(0) # Get only first symbol layer
                        fill = argb2abgr("%x" % symbLyr.color().rgba())
                        border = argb2abgr("%x" % symbLyr.strokeColor().rgba())
                        outline = symbLyr.strokeWidth()
                        styles.append([name, {"fill": fill,
                                              "outline": outline,
                                               "border": border}])
        elif rnd.type() == 'singleSymbol':
            symb = rnd.symbol()
            if lyrGeo == 0: ## Point case
                imgname = "color_style.png"
                symb.exportImage(os.path.join(self.tmpDir, imgname), "png",
                                 QSize(30, 30))
                styles.append(["style", {"iconfile": imgname}])
            elif lyrGeo == 1: ## Line case
                color = argb2abgr("%x" % symb.color().rgba())
                width = symb.width()
                styles.append(["style", {"color": color, "width": width}])
            elif lyrGeo == 2: ## Polygon case
                symbLyr = symb.symbolLayer(0) # Get only first symbol layer
                fill = argb2abgr("%x" % symbLyr.color().rgba())
                border = argb2abgr("%x" % symbLyr.strokeColor().rgba())
                outline = symbLyr.strokeWidth()
                styles.append(["style", {"fill": fill,
                                         "outline": outline,
                                         "border": border}])
        else:
            raise Exception("Wrong symbology: must be single or categorized")
            #self.finished.emit(False)

        self.styles = styles

    def getStylesNames(self):
        if hasattr(self, 'styles'):
            return([x[0] for x in self.styles])

    def updateProgress(self):
        progress = int(self.counter / float(self.totalCounter) * 100)
        self.progress(progress)

    def cleanup(self):
        ## Removes the temporary files created
        for style in self.styles:
            if "iconfile" in style[1]:
                os.remove(os.path.join(self.tmpDir, style[1]["iconfile"]))
        os.remove(os.path.join(self.tmpDir, "doc.kml"))

    def process(self):
        try:
            self.setStyles()

            self.processLayer()
            Kml = kml(self.layer.name())
            types = ["string" for x in self.exports]
            Kml.addSchema(self.layer.name(), self.exports, types)

            for item in self.styles:
                styId, kwargs = item
                kwargs["label"] = float(self.showLbl)
                Kml.addStyle(styId, **kwargs)

            style = self.styles[0][0]
            for i in range(len(self.data)):
                self.updateProgress()
                folder = self.featFolder[i]
                name = self.labels[i]
                coords = self.coords[i]
                if self.styleField is not None:
                    style = self.featStyles[i]
                fields = {}
                fields[self.layer.name()] = list(zip(self.exports, self.data[i]))
                ## TODO:Maybe add a warning input data must be single part
                Kml.addPlacemark(folder, name, style, coords, fields)
                self.counter += 1

            tmpKml = os.path.join(self.tmpDir, "doc.kml")
            fstream = open(tmpKml, "wb")
            kmlstr = Kml.generatekml()
            fstream.write(kmlstr)
            fstream.close()

            z = zipfile.ZipFile(self.outFile, "w")
            z.write(tmpKml, arcname="doc.kml")
            for styDict in [x[1] for x in self.styles]:
                if "iconfile" in styDict.keys():
                    filename = os.path.join(self.tmpDir, styDict["iconfile"])
                    z.write(filename, arcname=os.path.basename(filename))
            z.close()

            self.cleanup()
            self.updateProgress()

        except Exception as e:
            self.counter = self.totalCounter
            self.updateProgress()
            self.emitMsg(e.args[0], "error")
