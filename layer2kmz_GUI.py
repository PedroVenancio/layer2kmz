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
from PyQt5.QtCore import QSettings, QCoreApplication, QTranslator, qVersion
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction
from qgis.core import QgsProject

# Import the code for the dialog
from .layer2kmz_dialog import layer2kmzDialog
import os

# import kml process
from .layer2kmz_process import kmlprocess

class layer2kmzGUI(object):
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'layer2kmz_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = layer2kmzDialog(iface)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr('&layer2kmz')
        # TODO: We are going to let the user set this up in a future iteration
        if self.iface.pluginToolBar():
            self.toolbar = self.iface.pluginToolBar()
        else:
            self.toolbar = self.iface.addToolBar('layer2kmz')
        self.toolbar.setObjectName('layer2kmz')

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('layer2kmz', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToVectorMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/layer2kmz/icon.png'
        self.add_action(
            icon_path,
            text=self.tr('Layer to KMZ'),
            callback=self.run,
            parent=self.iface.mainWindow())


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginVectorMenu(
                self.tr('&layer2kmz'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    def run(self):
        # Update combos
        layerTree = QgsProject.instance().layerTreeRoot().findLayers()
        layers = [lyr.layer() for lyr in layerTree]
        ## show all vector layers in combobox
        allLayers = [lyr for lyr in layers if lyr.type() == 0]
        self.dlg.updateLayerCombo([lyr.name() for lyr in allLayers])

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            layerName = self.dlg.getVectorLayer()
            labelFld = self.dlg.getLabel()
            folderFld = self.dlg.getFolder()
            exportFld = self.dlg.getExports()
            outFile = self.dlg.getOutFile()
            showLbl = self.dlg.getShowLabel()


            # Get the layer object from active layers
            canvas = self.iface.mapCanvas()
            shownLayers = [x.name() for x in canvas.layers()]
            layer = canvas.layer(shownLayers.index(layerName))

            if layerName not in shownLayers:
                self.dlg.emitMsg("%s not found or inactive!" % layerName,
                             "warning")
            elif outFile == "":
                self.dlg.emitMsg("Choose an output kmz file!", "warning")

            elif exportFld== []:
                self.dlg.emitMsg("At least one field to export must be selected.",
                                 "warning")
            else:
                self.dlg.setProgressBar("Processing", "", 100)

                kmlproc = kmlprocess(layer, labelFld, folderFld, exportFld,
                                     showLbl, outFile, self.dlg.ProgressBar,
                                     self.dlg.emitMsg)
                kmlproc.process()
