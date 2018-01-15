# encoding: utf-8

import gvsig
import os
from gvsig import geom
from org.gvsig.fmap.geom import Geometry
from org.gvsig.fmap.geom import GeometryLocator
from org.gvsig.fmap.geom.aggregate import MultiPrimitive
from org.gvsig.fmap.geom.primitive import Polygon, Point
# Con geometrias normales se quedaria con el getGeometryType()
from es.unex.sextante.dataObjects import IVectorLayer
from gvsig.libs.toolbox import ToolboxProcess
from es.unex.sextante.gui import core
from es.unex.sextante.gui.core import NameAndIcon
#from es.unex.sextante.parameters import ParameterDataObject
#from es.unex.sextante.exceptions import WrongParameterTypeException
from es.unex.sextante.additionalInfo import AdditionalInfoVectorLayer
#from gvsig import logger
#from gvsig import LOGGER_WARN
#from es.unex.sextante.additionalInfo import AdditionalInfo
from org.gvsig.geoprocess.lib.api import GeoProcessLocator
from java.awt.geom import Point2D
from org.gvsig.tools import ToolsLocator

class SetZFromRaster(ToolboxProcess):
  def defineCharacteristics(self):
    i18nManager = ToolsLocator.getI18nManager()
    self.setName(i18nManager.getTranslation("_Assign_Z_value_to_geometries_from_raster")) #"Asignar coordenada Z en geometrias")
    self.setGroup(i18nManager.getTranslation("_Transform"))
    params = self.getParameters()
    self.setUserCanDefineAnalysisExtent(False)
    params.addInputVectorLayer("studyAreaNameVector",i18nManager.getTranslation("_Transform_Layer"), AdditionalInfoVectorLayer.SHAPE_TYPE_ANY,True)
    params.addInputRasterLayer("rasterStore",i18nManager.getTranslation("_Raster_for_Z_coordinate"), True)
    params.addFilepath("outputFilePath",i18nManager.getTranslation("_Output_Layer"),False,False,True,[".shp"])

  def processAlgorithm(self):
    params = self.getParameters()
    studyAreaNameVector = params.getParameterValueAsVectorLayer("studyAreaNameVector").getFeatureStore()
    rasterStore = params.getParameterValueAsRasterLayer("rasterStore").getBaseDataObject().getDataStore()

    outputFilePath = params.getParameterValueAsString("outputFilePath")
    if outputFilePath == "":
        outputFilePath = gvsig.getTempFile("result_geometries",".shp")
    elif not outputFilePath.endswith('.shp'):
        outputFilePath = outputFilePath+".shp"
    process(self,studyAreaNameVector,rasterStore,outputFilePath)
    return True

    
def process(selfStatus,store,raster,outputFilePath=None):
    # SELECT METHOD TO TRANSFORM POINTS
    method = "setZFromRaster" #None
    
    geomManager = GeometryLocator.getGeometryManager()
    
    if store.getFeatureSelection().getSize()>0:
        fset = store.getFeatureSelection()
    else:
        fset = store.getFeatureSet()
        
    nsch = gvsig.createFeatureType(store.getDefaultFeatureType())
    
    if method == "setZFromRaster":
        transformMethod = setZFromRaster
        subtype = geom.D3M
        
    nsch.get("GEOMETRY").setGeometryType(nsch.get("GEOMETRY").getGeometryType(), subtype)
    if outputFilePath is None:
        outputFilePath = gvsig.getTempFile("result_geometries",".shp")
    ns = gvsig.createShape(nsch,outputFilePath)
    ns.edit()
    store = ns.getFeatureStore()
    selfStatus.setRangeOfValues(0,fset.getSize())
    for f in fset:
        selfStatus.next()
        fg = f.getDefaultGeometry()
        #print "Default geometry: ", fg,
        if subtype == None: 
            subtype =  fg.getGeometryType().getSubType()
        nm = geomManager.create(fg.getGeometryType().getType(), subtype)
        if isinstance(fg,MultiPrimitive): # for multiprimitive
            for i in range(0,fg.getPrimitivesNumber()):
                iPol = fg.getPrimitiveAt(i)
                np = geomManager.create(iPol.getGeometryType().getType(), subtype)
                insertVertexFromGeometryInGeometry(iPol, np, raster, transformMethod) ## INSERT
                nm.addPrimitive(np)
        else: # for primitive
            insertVertexFromGeometryInGeometry(fg, nm, raster, transformMethod) ## INSERT
        
        nf = store.createNewFeature(f)
        nf.set("GEOMETRY", nm)
        store.insert(nf)
        
        if selfStatus.isCanceled() == True:
            ns.finishEditing()
            return True
    ns.finishEditing()
    gvsig.currentView().addLayer(ns)

def getZFromMDT(storeMDT, point, band=0):
    p = storeMDT.worldToRaster(Point2D.Double(point.getX(), point.getY()))
    try:
        z  = storeMDT.getData(int(p.getX()), int(p.getY()), 0)
    except:
        return 0
    return z
    
def setZFromRaster(iVertex,raster,nv=None):
    if nv is None:
        nv = GeometryLocator.getGeometryManager().create(iVertex.getGeometryType().getType(),Geometry.SUBTYPES.GEOM3DM)
    for d in range(0,iVertex.getDimension()):
            nv.setCoordinateAt(d,iVertex.getCoordinateAt(d))
    nv.setCoordinateAt(Geometry.DIMENSIONS.Z,getZFromMDT(raster,iVertex))
    return nv
    
def insertVertexFromGeometryInGeometry(iPol,np,raster,transformMethod=None):
    geomManager = GeometryLocator.getGeometryManager()
    if isinstance(iPol, Point):
        if transformMethod is None:
            for d in range(0,iPol.getDimension()):
                np.setCoordinateAt(d,iPol.getCoordinateAt(d))
            return
        else:
            transformMethod(iPol, raster, np)
            return
    
    for v in range(0, iPol.getNumVertices()):
        iVertex = iPol.getVertex(v)
        if transformMethod is None:
            nv = geomManager.create(iVertex.getGeometryType().getType(),iVertex.getGeometryType().getSubType())
            for d in range(0,iVertex.getDimension()):
                nv.setCoordinateAt(d,iVertex.getCoordinateAt(d))
        else:
            nv = transformMethod(iVertex,raster)
        np.addVertex(nv)

    
    if isinstance(iPol, Polygon):
        for r in range(0, iPol.getNumInteriorRings()):
            iRing = iPol.getInteriorRing(r)
            nr = geomManager.create(iRing.getGeometryType().getType(),iRing.getGeometryType().getSubType())
            insertVertexFromGeometryInGeometry(iRing, nr, raster,transformMethod)
            np.addInteriorRing(nr)

def main(*args):
    process = SetZFromRaster()
    process.selfregister("Scripting")
    process.updateToolbox()
    