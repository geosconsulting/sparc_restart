# -*- coding: utf-8 -*

#Standard Modules
import collections
import os
import sys

from osgeo import ogr
import matplotlib.pyplot as plt
import pylab
import numpy as np
import scipy.interpolate
import scipy.optimize
from scipy.interpolate import interp1d
import arcpy


arcpy.CheckOutExtension("spatial")
from arcpy import env
env.overwriteOutput = "true"

#Custom Modules
from intermedi.interfaces_discontinued import UtilitieSparc as us


class HazardAssessment(object):

    proj_dir = os.getcwd() + "/projects/"

    shape_countries = os.getcwd() + "/input_data/gaul/gaul_wfp_iso.shp"
    historical_accidents = os.getcwd() + "/input_data/historical_data/floods.csv"

    def __init__(self, paese, admin):

        self.dati_per_plot = {}
        self.dati_per_prob = {}
        self.paese = paese
        self.admin = admin
        self.dirOut = HazardAssessment.proj_dir + paese + "/" + admin + "/"

        scrittura_risultati = us.ConnectionPostgresDB(paese, admin)
        nome, iso2, iso3, wfp_area = scrittura_risultati.leggi_valori_amministrativi()

        self.wfp_area = str(wfp_area).strip()
        self.iso3 = iso3
        print "C:/data/tools/sparc/input_data/population/" + self.wfp_area + "/" + self.iso3 + "-POP/" + self.iso3 + "10.tif"

        #self.population_raster = "C:/sparc/input_data/population/" + self.wfp_area + "/" + self.iso3 + "-POP/" + self.iso3 + "10.tif"
        if os.path.isfile("C:/sparc/input_data/population/" + self.wfp_area + "/" + self.iso3 + "-POP/" + self.iso3 + "10.tif"):
            self.population_raster = "C:/sparc/input_data/population/" + self.wfp_area + "/" + self.iso3 + "-POP/" + self.iso3 + "10.tif"
        else:
            self.population_raster = "None"
            print "Population raster not yet released at http://www.worldpop.org.uk/...."
            sys.exit()

        self.flood_aggregated = "C:/sparc/input_data/flood/merged/" + self.paese + "_all_rp_rcl.tif"
        self.historical_accidents = "C:/sparc/input_data/historical_data/floods.csv"
        self.flood_directory = "C:/sparc/input_data/flood/m1/"
        self.flood_rp25 = self.flood_directory + paese + "_25_M1.grd"
        self.flood_rp50 = self.flood_directory + paese + "_50_M1.grd"
        self.flood_rp100 = self.flood_directory + paese + "_100_M1.grd"
        self.flood_rp200 = self.flood_directory + paese + "_200_M1.grd"
        self.flood_rp500 = self.flood_directory + paese + "_500_M1.grd"
        self.flood_rp1000 = self.flood_directory + paese + "_1000_M1.grd"

        self.flood_extents = []
        self.flood_extents.append(self.flood_rp25)
        self.flood_extents.append(self.flood_rp50)
        self.flood_extents.append(self.flood_rp100)
        self.flood_extents.append(self.flood_rp200)
        self.flood_extents.append(self.flood_rp500)
        self.flood_extents.append(self.flood_rp1000)

        if os.path.isfile("C:/sparc/input_data/geocoded/risk_map/" + self.paese + ".tif"):
            self.population_raster = "C:/sparc/input_data/population/" + self.wfp_area + "/" + self.iso3 + "-POP/" + self.iso3 + "10.tif" #popmap10.tif"
        else:
            self.population_raster = "None"
            print "Risk raster not available...."
            #sys.exit()

    def estrazione_poly_admin(self):

        filter_field_name = "ADM2_NAME"

        # Get the input Layer
        inDriver = ogr.GetDriverByName("ESRI Shapefile")
        inDataSource = inDriver.Open(self.shape_countries, 0)
        inLayer = inDataSource.GetLayer()

        inLayer.SetAttributeFilter("ADM2_NAME = '" + self.admin + "'")
        numFeatures = inLayer.GetFeatureCount()

        # Create the output LayerS
        outShapefile = os.path.join(self.dirOut + self.admin + ".shp")
        outDriver = ogr.GetDriverByName("ESRI Shapefile")

        # Remove output shapefile if it already exists
        if os.path.exists(outShapefile):
            outDriver.DeleteDataSource(outShapefile)

        # Create the output shapefile
        outDataSource = outDriver.CreateDataSource(outShapefile)
        out_lyr_name = os.path.splitext( os.path.split(outShapefile)[1])[0]
        outLayer = outDataSource.CreateLayer(out_lyr_name, geom_type=ogr.wkbMultiPolygon)

        # Add input Layer Fields to the output Layer if it is the one we want
        inLayerDefn = inLayer.GetLayerDefn()
        for i in range(0, inLayerDefn.GetFieldCount()):
            fieldDefn = inLayerDefn.GetFieldDefn(i)
            fieldName = fieldDefn.GetName()
            if fieldName not in filter_field_name:
                continue
            outLayer.CreateField(fieldDefn)

        # Get the output Layer's Feature Definition
        outLayerDefn = outLayer.GetLayerDefn()

        # Add features to the ouput Layer
        for inFeature in inLayer:
            # Create output Feature
            outFeature = ogr.Feature(outLayerDefn)

            # Add field values from input Layer
            for i in range(0, outLayerDefn.GetFieldCount()):
                fieldDefn = outLayerDefn.GetFieldDefn(i)
                fieldName = fieldDefn.GetName()
                if fieldName not in filter_field_name:
                    continue
                outFeature.SetField(outLayerDefn.GetFieldDefn(i).GetNameRef(),
                    inFeature.GetField(i))

            # Set geometry as centroid
            geom = inFeature.GetGeometryRef()
            outFeature.SetGeometry(geom.Clone())

            # Add new feature to output Layer
            outLayer.CreateFeature(outFeature)

        # Close DataSources
        inDataSource.Destroy()
        outDataSource.Destroy()
        return "Admin extraction......\n"

    def conversione_vettore_raster_admin(self):

        global admin_vect
        admin_vect = self.dirOut + self.admin + ".shp"

        global admin_rast
        if len(self.admin) > 5:
            admin = self.admin[0:3]
        admin_rast = self.dirOut + self.admin + "_rst.tif"
        print admin_rast

        try:
            admin_rast = arcpy.PolygonToRaster_conversion(admin_vect, "ADM2_NAME", admin_rast, "CELL_CENTER", "NONE", 0.0008333)
        except Exception as e:
            print e.message

        return "Raster Created....\n"

    def taglio_raster_popolazione(self):

        # #CUT and SAVE Population within the admin2 area
        # lscan_out_rst = arcpy.Raster(self.population_raster) * arcpy.Raster(admin_rast)
        # lscan_out = self.dirOut + self.admin + "_pop.tif"
        # lscan_out_rst.save(lscan_out)
        # return "Population clipped....\n"
        if self.population_raster!= "None":
            lscan_out_rst = arcpy.Raster(self.population_raster) * arcpy.Raster(admin_rast)
            lscan_out = self.dirOut + self.admin + "_pop.tif"
            lscan_out_rst.save(lscan_out)
            return "sipop"
        else:
            return "nopop"


    def taglio_raster_inondazione_aggregato(self):

        #CUT and SAVE Flooded areas within the admin2 area
        flood_out_rst = arcpy.Raster(self.flood_aggregated) * arcpy.Raster(admin_rast)
        flood_out = self.dirOut + self.admin + "_agg.tif"
        flood_out_rst.save(flood_out)
        return "Flood hazard aggregated clipped....\n"

    def taglio_raster_inondazione(self):

        for rp in self.flood_extents:
            #CUT and SAVE Flooded areas within the admin2 area
            flood_divided_rst = arcpy.Raster(rp) * arcpy.Raster(admin_rast)
            flood_out_divided = self.dirOut + rp.split("/")[7].split("_")[1] + "_fld.tif"
            flood_divided_rst.save(flood_out_divided)

        return "Clipped all floods.......\n"

    def calcolo_statistiche_zone_indondazione(self):

        flood_out = arcpy.Raster(self.dirOut + self.admin + "_agg.tif")
        pop_out = arcpy.Raster(self.dirOut + self.admin + "_pop.tif")
        pop_stat_dbf = self.dirOut + self.admin.lower() + "_pop_stat.dbf"
        global tab_valori
        tab_valori = arcpy.gp.ZonalStatisticsAsTable_sa(flood_out, "Value", pop_out, pop_stat_dbf ,"DATA","ALL")
        global pop_freqs
        pop_freqs = arcpy.da.SearchCursor(tab_valori,["Value", "SUM"])
        return "People in flood prone areas....\n"

    def plot_affected(self):

        titolofinestra = "People Living in Flood Prone Areas"

        print(pop_freqs)

        # Plotting affected people
        affected_people = {}
        for row in pop_freqs:
            affected_people[row[0]] = row[1]

        global affected_people_ordered
        affected_people_ordered = collections.OrderedDict(sorted(dict(affected_people).items()))

        fig = pylab.gcf()
        fig.canvas.set_window_title(titolofinestra)

        plt.grid(True)
        plt.title(self.admin)
        plt.xlabel("Return Periods")
        plt.ylabel("People in Flood Prone Area WorldPop 2010")
        plt.bar(range(len(affected_people_ordered)), affected_people_ordered.values(), align='center')
        plt.xticks(range(len(affected_people_ordered)), affected_people_ordered.keys())
        plt.show()
        return affected_people

    def plot_risk_curve(self):

        print affected_people_ordered

        pop_temp = 0
        for periodo in affected_people_ordered.iteritems():
            annual_perc = 1/(periodo[0]/100.0)
            pop_temp = pop_temp + periodo[1]
            self.dati_per_plot[annual_perc] = pop_temp
            self.dati_per_prob[periodo[0]] = pop_temp

        fig = pylab.gcf()
        fig.canvas.set_window_title("Risk Curve")
        plt.grid(True)
        plt.title("Risk Curve using 6 Return Periods")
        plt.xlabel("Affected People", color="red")
        plt.ylabel("Annual Probabilities %", color="red")
        plt.tick_params(axis="x", labelcolor="b")
        plt.tick_params(axis="y", labelcolor="b")
        plt.plot(sorted(self.dati_per_plot.values(), reverse=True), sorted(self.dati_per_plot.keys()), 'ro--')
        for x, y in self.dati_per_plot.iteritems():
            plt.annotate(str(int(round(y, 2))), xy=(y, x), xytext=(5, 5), textcoords='offset points', color='red', size=8)
        plt.show()

    def plot_risk_interpolation(self):

        print self.dati_per_plot
        x, y = self.dati_per_plot.keys(),  self.dati_per_plot.values()

        # use finer and regular mesh for plot
        xfine = np.linspace(0.1, 4, 25)

        # interpolate with piecewise constant function (p =0)
        y0 = scipy.interpolate.interp1d(x, y, kind='nearest')

        # interpolate with piecewise linear func (p =1)
        y1 = scipy.interpolate.interp1d(x, y, kind='linear')

        plt.grid(True)
        pylab.plot(x, y, 'o', label='Affected People')
        pylab.plot(xfine, y0(xfine), label='nearest')
        pylab.plot(xfine, y1(xfine), label='linear')

        pylab.legend()
        pylab.xlabel('x')

        #pylab.savefig('interpolate.pdf')
        pylab.show()

    def interpolazione_tempi_ritorno_intermedi(self):

        print(self.dati_per_prob)

        dict_data = dict(self.dati_per_prob)
        dict_data_new = dict_data.copy()

        xdata = dict_data.keys()
        ydata = dict_data.values()

        f = interp1d(xdata, ydata)

        nuovi_RP = [75, 150, 250, 750]
        for xnew in nuovi_RP:
            popolazione_interpolata = f(xnew)
            dict_data_new[xnew] = float(popolazione_interpolata)
        ordinato_old = collections.OrderedDict(sorted(dict(dict_data).items()))
        global ordinato_new
        ordinato_new = collections.OrderedDict(sorted(dict(dict_data_new).items()))

    def gira_dati(self):
        global data_prob
        data_prob = {}
        for giratore in ordinato_new.iterkeys():
            data_prob[(1.0/giratore)*100] = ordinato_new[giratore]

    def plot_risk_interpolation_linear(self):

        print(data_prob)
        titolo_plot = "Risk Curve using RP 25,50,75,100,150,200,500,750 and 1000 Years"
        x, y = data_prob.keys(), data_prob.values()
        xfine = np.linspace(0.1, 4, 25)
        y1 = scipy.interpolate.interp1d(x, y, kind='linear')
        plt.grid(True)

        fig = pylab.gcf()
        fig.canvas.set_window_title(titolo_plot)
        plt.grid(True)
        plt.title(self.admin)

        pylab.plot(x, y, 'o', label='Affected People')
        pylab.plot(xfine, y1(xfine), label='linear')

        for x, y in data_prob.iteritems():
            plt.annotate(str(int(round(y, 2))), xy=(y,x), xytext=(5,5), textcoords='offset points', color='red', size=8)

        pylab.legend()
        pylab.xlabel('x')
        #pylab.savefig('interpolate.pdf')
        pylab.show()