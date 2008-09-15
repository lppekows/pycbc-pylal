#!/usr/bin/env python
"""
Something

$Id$

This program generates a detection checklist for a candidate.
"""

__author__ = 'Romain Gouaty <romain@phys.lsu.edu>'
__date__ = '$Date$'
__version__ = '$Revision$'[11:-2]

##############################################################################
# import standard modules and append the lalapps prefix to the python path
import sys, os, copy, math, random
import socket, time
import re, string
import commands
from optparse import *
import tempfile
import ConfigParser
import urlparse
import urllib
from UserDict import UserDict
sys.path.append('@PYTHONLIBDIR@')

##############################################################################
# import the modules we need to build the pipeline
from glue import lal
from glue import segments
from glue import segmentsUtils
from glue.ligolw import ligolw
from glue.ligolw import table
from glue.ligolw import lsctables
from glue.ligolw import utils
from pylal import CoincInspiralUtils
from pylal.fu_utils import *
from pylal.fu_writeXMLparams import *
from pylal.webUtils import *
from pylal import Fr
from pylal.scrapeHtmlUtils import scrapePage
from lalapps import inspiral

######################## OPTION PARSING  #####################################
usage = """usage: %prog [options]
"""

parser = OptionParser( usage )

parser.add_option("-v", "--version",action="store_true",default=False,\
    help="print version information and exit")

parser.add_option("-f","--xml-file",action="store",type="string",\
    metavar=" FILE",help="specify path to the xml file containing the list of candidates to be followed-up")

parser.add_option("-n","--num-triggers",action="store",type="int",\
    metavar=" VALUE",help="number of triggers to followup")

parser.add_option("-s","--statistic",action="store",type="string",\
    metavar=" STRING",help="use statistic STRING to sort triggers (ex: effective_snrsq)")

parser.add_option("-a","--bla",action="store",type="float",\
    metavar=" VALUE",help="bitten l a")

parser.add_option("-b","--blb",action="store",type="float",\
    metavar=" VALUE",help="bitten l b")

parser.add_option("-A","--automated-page",action="store",type="string",\
    metavar=" STRING",help="url of the automated follow-up page")

parser.add_option("","--old-followup-page",action="store",type="string",\
    metavar=" STRING",help="url to the old checklist (optional)")

parser.add_option("-S","--statistic-page",action="store",type="string",\
    metavar=" STRING",help="url of the statistic page")

parser.add_option("-C","--cumulhisto-page",action="store",type="string",\
    metavar=" STRING",help="url to the cumulative histogram of combined statistics")

parser.add_option("-H","--histo-page",action="store",type="string",\
    metavar=" STRING",help="url to the histogram of combined statistics")

parser.add_option("-I","--ifar-page",action="store",type="string",\
    metavar=" STRING",help="url to the ifar plot")

parser.add_option("","--ifar-combined-page",action="store",type="string",\
    metavar=" STRING",help="url to the combined ifar plot")

parser.add_option("-q","--qscan-page",action="store",type="string",\
    metavar=" STRING",help="basic url of the qscan pages.\n Example: \"http://ldas-jobs.ligo.caltech.edu/~romain/S5_followup/LowMassCBC/20051104-20061114/full_zerolag/\"\n WARNING: This script makes the assumption that the qscan subdirectories are chosen following the convention \"qscantype/ifo/\", where qscantype is one of [qscan, hoft-qscan, seismic-qscan] and ifo is one of [H1,H2,L1]")

parser.add_option("-Q","--qscan-dir",action="store",type="string",\
    metavar=" STRING",help="path to the qscan output directories.\n Example: \"/archive/home/romain/public_html/S5_followup/LowMassCBC/20051104-20061114/full_zerolag/\"")

parser.add_option("","--string-id",action="store",type="string",\
    metavar=" STRING",help="string which allows to identify the veto category and the mass bin in which these candidates have been found.\n An example would be: \"cat12_17-35\", for candidates found after cat12 vetoes in the 17-35 mass bin.\n This argument is used when writing text in the checklist, but can be safely omitted")

command_line = sys.argv[1:]
(opts,args) = parser.parse_args()

#################################
# if --version flagged
if opts.version:
  print "$Id: generate_checklist.py, v 1.0 2008/05/20 07:00:00 romain Exp"
  sys.exit(0)

##############################################################################
# main program

# List of ifos (used to check for Nelson KW vetoes)
ifoList = ['H1','H2','L1']

stat = opts.statistic
if stat == "effective_snrsq":
  stat = "effective_snr"

found, coincs, search = readFiles(opts.xml_file,getstatistic(opts.statistic,opts.bla,opts.blb))

followuptrigs = getfollowuptrigs(str(opts.num_triggers),None,coincs,None,search,None)

for i,trig in enumerate(followuptrigs):
  gpsTime = trig.gpsTime[trig.ifolist_in_coinc[0]]
  gps_int = int(gpsTime)

  # get the path to the qscan "context.html" file which will be parsed to get the DQ information
  qscanContextFile = os.path.normpath(opts.qscan_dir + "/hoft-qscan/" + trig.ifolist_in_coinc[0] + "/" + repr(gpsTime) + "/context.html")

  qscanContextForDQ = scrapePage()
  DQflagsTable = scrapePage()
  # specify the context keys to select the Data_Quality table
  # from the qscan context.html file.
  qscanContextForDQ.setContextKeys(\
        "<div id=\"div_Data_Quality\" style=\"display: block;\">",\
        "<a name=\"Detector_Logs\"></a>")
  # Read qscan "context.html" file into memory
  qscanContextForDQ.readfile(qscanContextFile)
  # copy the rows from the Data_Quality table.
  # if the row contains the string "Science" it must be stripped off from the DQ table.
  for row in qscanContextForDQ.tableObject:
    if row.__len__() > 3:
      if not row[2].__contains__("Science"):
        DQflagsTable.tableObject.append(row)

  dateDQflags = commands.getoutput("grep \"Data quality flags\" -A 3 -i " + qscanContextFile + " | grep \"(as of\"")

  qscanContextForSc = scrapePage()
  ScSegTable = scrapePage()
  # specify the context keys to select the Segments table
  # from the qscan context.html file.
  qscanContextForSc.setContextKeys(\
        "<div id=\"div_Segments\" style=\"display: block;\">",\
        "<a name=\"Data_Quality\"></a>")
  # Read qscan "context.html" file into memory
  qscanContextForSc.readfile(qscanContextFile)
  # copy the rows from the Segments table.
  for row in qscanContextForSc.tableObject:
    if row.__len__() > 3:
      ScSegTable.tableObject.append(row)

  dateScSeg = commands.getoutput("grep \"Detector state\" -A 3 -i " + qscanContextFile + " | grep \"(as of\"") 

  outputFile = "followup_" + str(gps_int) + ".html"
  file = open(outputFile,'w')

  file.write("<!DOCTYPE html PUBLIC \"-//W3C//DTD HTML 4.01 Transitional//EN\"> \
  <%method cvsid>$Id$</%method>\n")
  file.write("<html><head> \
  <meta content=\"text/html; charset=ISO-8859-1\" http-equiv=\"content-type\"> \
  <title>Candidate</title></head><body>\n\n")

  file.write("<h1>Candidate followup:</h1>\n")
  file.write("<h3>Inspiral triggers found by the CBC low mass search:</h3>\n\n")
  file.write("<table style=\"text-align: left; height: 259px; width: 100%;\" id=\"table\" border=\"1\">\n")
  file.write("<tbody>\n\n<tr>\n")
  file.write("    <th>IFO</th>\n \
    <th>End Time</th>\n \
    <th>SNR</th>\n \
    <th>CHISQ</th>\n \
    <th>Chirp Mass</th>\n \
    <th>Eta</th>\n \
    <th>Mass 1</th>\n \
    <th>Mass 2</th>\n \
    <th>Eff Dist (Mpc)</th>\n</tr>\n\n")

  for ifo in trig.ifolist_in_coinc:
    file.write("<tr><td><p>" + ifo + "</p>\n")
    file.write("</td><td><p>" + repr(trig.gpsTime[ifo]) + "</p>\n")
    file.write("</td><td><p>" + str(getattr(trig.coincs,ifo).snr) + "</p>\n")
    file.write("</td><td><p>" + str(getattr(trig.coincs,ifo).chisq) + "</p>\n")
    file.write("</td><td><p>" + str(getattr(trig.coincs,ifo).mchirp) + "</p>\n")
    file.write("</td><td><p>" + str(getattr(trig.coincs,ifo).eta) + "</p>\n")
    file.write("</td><td><p>" + str(getattr(trig.coincs,ifo).mass1) + "</p>\n")
    file.write("</td><td><p>" + str(getattr(trig.coincs,ifo).mass2) + "</p>\n")
    file.write("</td><td><p>" + str(getattr(trig.coincs,ifo).eff_distance) + "</p>\n")
    file.write("</td></tr>\n")

  file.write("\n</tbody>\n</table>\n\n")

  if not opts.automated_page.find("index.html"):
    linkToAutoFollowup = opts.automated_page + "/index.html#section" + str(i)
    automated_page = opts.automated_page
  else:
    linkToAutoFollowup = opts.automated_page
    automated_page = opts.automated_page.split("index.html")[0]
  file.write("<br><a href=\"" + linkToAutoFollowup + "\">Automated follow-up</a>")
  if opts.statistic_page:
    linkToStat = opts.statistic_page 
    file.write("<br><a href=\"" + linkToStat + "\">Statistical information</a>\n")
  if opts.old_followup_page:
    file.write("<br><a href=\"" + opts.old_followup_page + "/" + outputFile + "\">Link to old checklist</a>\n")

  n_veto = nVeto()
  nelsonVeto = []
  dailyStat = []
  hoft_qscan = []
  rds_qscan = []
  seis_qscan = []
  analyse_rds_qscan = []
  analyse_seismic_qscan = []
  snrchisq = []
  coherent_qscan = []
  framecheck = []

  # prepare strings containing information on Nelson's DQ investigations
  for ifo in ifoList:
    if ifo in trig.ifolist_in_coinc:
      nelsonVeto.append(n_veto.findInterval(ifo,trig.gpsTime[ifo]))
    else:
      nelsonVeto.append(n_veto.findInterval(ifo,trig.gpsTime[trig.ifolist_in_coinc[0]]))

  for ifo in trig.ifolist_in_coinc:

    # links to daily stats
    dailyStat.append(automated_page + "/IFOstatus_checkJob/IFOstatus_checkJob-" + ifo + "-" + str(trig.statValue) + "_" + str(trig.eventID) + ".html")

    # links to qscans
    hoft_qscan.append(opts.qscan_page + "/hoft-qscan/" + ifo + "/" + repr(trig.gpsTime[ifo]))
    rds_qscan.append(opts.qscan_page + "/qscan/" + ifo + "/" + repr(trig.gpsTime[ifo]))
    seis_qscan.append(opts.qscan_page + "/seismic-qscan/" + ifo + "/" + repr(trig.gpsTime[ifo]))
    
    # links to analyse qscans
    analyse_seismic_qscan.append(automated_page + "/analyseQscanJob/" + ifo + "-foreground-seismic-qscan-" + repr(trig.gpsTime[ifo]) + ".html")
    analyse_rds_qscan.append(automated_page + "/analyseQscanJob/" + ifo + "-foreground-qscan-" + repr(trig.gpsTime[ifo]) + ".html")

    # links to snrchisq plots
    snrchisq.append(automated_page + "/plotSNRCHISQJob/plotSNRCHISQJob-" + ifo + "-" + str(trig.statValue) + "_" + str(trig.eventID) + ".html")

    # links to frame checks
    framecheck.append(automated_page + "/FrCheckJob/FrCheckJob-" + ifo + "-" + str(trig.statValue) + "_" + str(trig.eventID) + ".html")

  # loop over ifos not found in coincidence (though in the analysed times)
  for j in range(0,len(trig.ifoTag)-1,2):
    ifo = trig.ifoTag[j:j+2]
    if not trig.ifolist_in_coinc.count(ifo):
       # links to qscans
       hoft_qscan.append(opts.qscan_page + "/hoft-qscan/" + ifo + "/" + repr(trig.gpsTime[trig.ifolist_in_coinc[0]]))
       rds_qscan.append(opts.qscan_page + "/qscan/" + ifo + "/" + repr(trig.gpsTime[trig.ifolist_in_coinc[0]]))
       # links to snrchisq plots
       for ifo_ref in trig.ifolist_in_coinc:
         snrchisq.append(automated_page + "/plotSNRCHISQJob/plotSNRCHISQJob-" + ifo + "-" + ifo_ref + "tmplt-" + str(trig.statValue) + "_" + str(trig.eventID) + ".html")

  # link to coherent qscan
  try:
    trig.ifolist_in_coinc.index("H1")
    trig.ifolist_in_coinc.index("H2")
    coherent_qscan.append(opts.qscan_page + "qevent/H1H2/" + repr(trig.gpsTime["H1"]))
  except: pass


  # build the checklist table
  file.write("\n<br>\n<h3>Follow-up tests</h3>\n<table style=\"text-align: left; height: 259px; width: 100%;\" border=\"1\" cellpadding=\"2\" cellspacing=\"2\">\n\n<tbody>\n\n")
  file.write("<tr>\n")
  file.write("  <td>ID</td>\n")
  file.write("  <td>Questions</td>\n")
  file.write("  <td>Answers</td>\n")
  file.write("  <td>Relevant information (flags, plots and links)</td>\n")
  file.write("  <td>Comments</td>\n")
  file.write("</tr>\n\n")

  file.write("<tr bgcolor=red>\n")
  file.write("  <td> </td>\n")
  file.write("  <td><b>Is this candidate a possible gravitational-wave ?</b></td>\n")
  file.write("  <td><b>YES/NO</b></td>\n")
  file.write("  <td> </td>\n")
  file.write("  <td>Main arguments</td>\n")
  file.write("</tr>\n\n")

  # Row #0
  file.write("<tr>\n")
  file.write("  <td>#0 False alarm probability</td>\n")
  file.write("  <td>What is the false alarm rate associated with this candidate ?</td>\n")
  file.write("  <td> </td>\n")
  file.write("  <td>")
  if opts.string_id:
    if opts.cumulhisto_page:
      file.write("      <a href=\"" + opts.cumulhisto_page + "\">Cumulative histogram (after " + opts.string_id.split("_")[0] + ", " + opts.string_id.split("_")[1] + " mass bin)</a><br>\n")
    if opts.histo_page:
      file.write("      <a href=\"" + opts.histo_page + "\">Non-cumulative histogram (after " + opts.string_id.split("_")[0] + ", " + opts.string_id.split("_")[1] + " mass bin)</a><br>\n")
    if opts.ifar_page:
      file.write("      <a href=\"" + opts.ifar_page + "\">IFAR plot (after " + opts.string_id.split("_")[0] + ", " + opts.string_id.split("_")[1] + " mass bin)</a><br>\n")
    if opts.ifar_combined_page:
      file.write("      <a href=\"" + opts.ifar_combined_page + "\">Combined IFAR plot (after " + opts.string_id.split("_")[0] + ", " + opts.string_id.split("_")[1] + " mass bin)</a><br>\n")
  else:
    if opts.cumulhisto_page:
      file.write("      <a href=\"" + opts.cumulhisto_page + "\">Cumulative histogram</a><br>\n")
    if opts.histo_page:
      file.write("      <a href=\"" + opts.histo_page + "\">Non-cumulative histogram</a><br>\n")
    if opts.ifar_page:
      file.write("      <a href=\"" + opts.ifar_page + "\">IFAR plot</a><br>\n")
    if opts.ifar_combined_page:
      file.write("      <a href=\"" + opts.ifar_combined_page + "\">Combined IFAR plot</a><br>\n")
  file.write("  </td>\n")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #1
  file.write("<tr>\n")
  file.write("  <td>#1 DQ flags</td>\n")
  file.write("  <td>Can the data quality flags coincident with this candidate be safely disregarded ?</td>\n")
  file.write("  <td></td>\n")
  file.write("  <td>" + DQflagsTable.buildTableHTML("border=1 bgcolor=yellow").replace("\n","") + "<br>" + dateDQflags + "</td>\n")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #2
  file.write("<tr>\n")
  file.write("  <td>#2 Veto investigations</td>\n")
  file.write("  <td>Does the candidate survive the veto investigations performed at its time ?</td>\n")
  file.write("  <td></td>\n")
  file.write("  <td>")
  for j,ifo in enumerate(ifoList):
    file.write("<table>")
    file.write("\n<b>" + ifo + ":</b>\n")
    file.write('<tr><td>' + nelsonVeto[j].strip("\n").replace("\n","</td></tr><tr><td>").replace(" ", "</td><td>") + '</td></tr>')
    file.write("</table>")
  file.write("</td>\n")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #3
  file.write("<tr>\n")
  file.write("  <td>#3 Ifo status</td>\n")
  file.write("  <td>Are the interferometers operating normally with a reasonable level of sensitivity around the time of the candidate ?</td>\n")
  file.write("  <td></td>\n")
  file.write("  <td><a href=\"http://blue.ligo-wa.caltech.edu/scirun/S5/DailyStatistics/\">Daily Stats pages</a>:")
  for j,ifo in enumerate(trig.ifolist_in_coinc):
    file.write(" <a href=\"" + dailyStat[j] + "\">" + ifo + "</a>")
  file.write("\n" + ScSegTable.buildTableHTML("border=1 bgcolor=green").replace("\n","") + "<br>" + dateScSeg)
  file.write("  </td>")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #4
  file.write("<tr>\n")
  file.write("  <td>#4 Candidate appearance</td>\n")
  file.write("  <td>Do the Qscan figures show what we would expect for a gravitational-wave event ?</td>\n")
  file.write("  <td></td>\n")
  file.write("  <td>h(t) Qscans:<br>")
  for j,ifo in enumerate(trig.ifolist_in_coinc):
    file.write(" <a href=\"" + hoft_qscan[j] + "\">" + ifo + "</a><br>")
    file.write(" <img src=\"" + hoft_qscan[j] + "/" + repr(trig.gpsTime[ifo]) + "_" + ifo + ":LSC-STRAIN_1.00_spectrogram_whitened_thumbnail.png\" width=\"50%\">")
    file.write(" <img src=\"" + hoft_qscan[j] + "/" + repr(trig.gpsTime[ifo]) + "_" + ifo + ":LSC-STRAIN_16.00_spectrogram_whitened_thumbnail.png\" width=\"50%\"><br><br>")
  i=0
  for k in range(0,len(trig.ifoTag)-1,2):
    ifo = trig.ifoTag[k:k+2]
    if not trig.ifolist_in_coinc.count(ifo):
      i=i+1
      file.write(" <a href=\"" + hoft_qscan[i + len(trig.ifolist_in_coinc) - 1] + "\">" + ifo + "</a><br>")
      file.write(" <img src=\"" + hoft_qscan[i + len(trig.ifolist_in_coinc) - 1] + "/" + repr(trig.gpsTime[trig.ifolist_in_coinc[0]]) + "_" + ifo + ":LSC-STRAIN_1.00_spectrogram_whitened_thumbnail.png\" width=\"50%\">")
      file.write(" <img src=\"" + hoft_qscan[i + len(trig.ifolist_in_coinc) - 1] + "/" + repr(trig.gpsTime[trig.ifolist_in_coinc[0]]) + "_" + ifo + ":LSC-STRAIN_16.00_spectrogram_whitened_thumbnail.png\" width=\"50%\"><br><br>")
  file.write("  </td>")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #5
  file.write("<tr>\n")
  file.write("  <td>#5 Seismic plots</td>\n")
  file.write("  <td>Is the seismic activity insignificant around the time of the candidate ? </td>\n")
  file.write("  <td></td>\n")
  file.write("  <td>Seismic Qscans:")
  for j,ifo in enumerate(trig.ifolist_in_coinc):
    file.write(" <a href=\"" + seis_qscan[j] + "\">" + ifo + "</a>")
  file.write("<br>Background information on qscans:")
  for j,ifo in enumerate(trig.ifolist_in_coinc):
    file.write(" <a href=\"" + analyse_seismic_qscan[j] + "\">" + ifo + "</a>")
  file.write("  </td>")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #6
  file.write("<tr>\n")
  file.write("  <td>#6 Other environmental causes</td>\n")
  file.write("  <td>Were the environmental disturbances (other than seismic) insignificant at the time of the candidate ?</td>\n")
  file.write("  <td></td>\n")
  file.write("  <td>RDS Qscans:")
  for j,ifo in enumerate(trig.ifolist_in_coinc):
    file.write(" <a href=\"" + rds_qscan[j] + "\">" + ifo + "</a>")
  i=0
  for k in range(0,len(trig.ifoTag)-1,2):
    ifo = trig.ifoTag[k:k+2]
    if not trig.ifolist_in_coinc.count(ifo):
      i=i+1
      file.write(" <a href=\"" + rds_qscan[i + len(trig.ifolist_in_coinc) - 1] + "\">" + ifo + "</a>")
  file.write("<br>Background information on qscans:")
  for j,ifo in enumerate(trig.ifolist_in_coinc):
    file.write(" <a href=\"" + analyse_rds_qscan[j] + "\">" + ifo + "</a>")
  file.write("  </td>")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #7
  file.write("<tr>\n")
  file.write("  <td>#7 Auxiliary degree of freedom</td>\n")
  file.write("  <td>Were the auxiliary channel transients coincident with the candidate insignificant ?</td>\n")
  file.write("  <td></td>\n")
  file.write("  <td>RDS Qscans:")
  for j,ifo in enumerate(trig.ifolist_in_coinc):
    file.write(" <a href=\"" + rds_qscan[j] + "\">" + ifo + "</a>")
  i=0
  for k in range(0,len(trig.ifoTag)-1,2):
    ifo = trig.ifoTag[k:k+2]
    if not trig.ifolist_in_coinc.count(ifo):
      i=i+1
      file.write(" <a href=\"" + rds_qscan[i + len(trig.ifolist_in_coinc) - 1] + "\">" + ifo + "</a>")
  file.write("<br>Background information on qscans:")
  for j,ifo in enumerate(trig.ifolist_in_coinc):
    file.write(" <a href=\"" + analyse_rds_qscan[j] + "\">" + ifo + "</a>")
  file.write("  </td>")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #8
  file.write("<tr>\n")
  file.write("  <td>#8 Elog</td>\n")
  file.write("  <td>Were the instruments behaving normally according to the comments posted by the sci-mons or the operators in the e-log ?</td>\n")
  file.write("  <td></td>\n")
  file.write("  <td><a href=\"http://ilog.ligo-wa.caltech.edu/ilog/pub/ilog.cgi?group=detector\">Hanford elog</a><br>\n")
  file.write("      <a href=\"http://ilog.ligo-la.caltech.edu/ilog/pub/ilog.cgi?group=detector\">Livingston elog</a></td>\n")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #9
  file.write("<tr>\n")
  file.write("  <td>#9 Glitch report</td>\n")
  file.write("  <td>Were the instruments behaving normally according to the weekly glitch report ?</td>\n")
  file.write("  <td></td>\n")
  file.write("  <td><a href=\"http://www.lsc-group.phys.uwm.edu/glitch/investigations/s5index.html#shift\">Glitch reports</a><br></td>\n")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #10
  file.write("<tr>\n")
  file.write("  <td>#10 Snr versus time</td>\n")
  file.write("  <td>Is this trigger significant in a SNR versus time plot of all triggers in its analysis chunk ?</td>\n")
  file.write("  <td></td>\n")
  file.write("  <td></td>\n")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #11
  file.write("<tr>\n")
  file.write("  <td>#11 Parameters of the candidate</td>\n")
  file.write("  <td>Does the candidate have a high likelihood of being a gravitational-wave according to its parameters ?<br></td>\n")
  file.write("  <td></td>\n")
  file.write("  <td></td>\n")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #12
  file.write("<tr>\n")
  file.write("  <td>#12 Snr and Chisq</td>\n")
  file.write("  <td>Are the SNR and CHISQ time series consistent with our expectations for a gravitational wave ?</td>\n")
  file.write("  <td></td>\n")
  file.write("  <td>")
  for j,ifo in enumerate(trig.ifolist_in_coinc):
    file.write(" <a href=\"" + snrchisq[j] + "\">" + ifo + "</a>")
  file.write("<br>\n")
  i=0
  for k in range(0,len(trig.ifoTag)-1,2):
    ifo = trig.ifoTag[k:k+2]
    if not trig.ifolist_in_coinc.count(ifo):
      for ifo_ref in trig.ifolist_in_coinc:
        i=i+1
        file.write(" <a href=\"" + snrchisq[i + len(trig.ifolist_in_coinc) - 1] + "\">" + ifo + " with " + ifo_ref + " template" + "</a>")
  file.write("  </td>\n")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #13
  file.write("<tr>\n")
  file.write("  <td>#13 Template bank veto</td>\n")
  file.write("  <td>Is the bank veto value consistent with our expectations for a gravitational wave ?</td>\n")  
  file.write("  <td></td>\n")
  file.write("  <td></td>\n")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #14
  file.write("<tr>\n")
  file.write("  <td>#14 Coherent studies</td>\n")
  file.write("  <td>Are the triggers found in multiple interferometers coherent with each other ?</td>\n")
  file.write("  <td></td>\n")
  if coherent_qscan:
    file.write("  <td><a href=\"" + coherent_qscan[0] + "\">H1H2 coherent qevent</a></td>\n")
  else: 
    file.write("  <td></td>\n")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #15
  file.write("<tr>\n")
  file.write("  <td>#15</td>\n")
  file.write("  <td>Is the candidate stable against changes in segmentation ?</td>\n")
  file.write("  <td></td>\n")
  file.write("  <td></td>\n")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #16
  file.write("<tr>\n")
  file.write("  <td>#16</td>\n")
  file.write("  <td>Is the candidate stable against changes in calibration that are consistent with systematic uncertainties ?</td>\n")
  file.write("  <td></td>\n")
  file.write("  <td></td>\n")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #17
  file.write("<tr>\n")
  file.write("  <td>#17</td>\n")
  file.write("  <td>Is the data used in the analysis free from corruption at the time of the candidate ?</td>\n")
  file.write("  <td></td>\n")
  file.write("  <td>Frame checks: ")
  for j,ifo in enumerate(trig.ifolist_in_coinc):
    file.write(" <a href=\"" + framecheck[j] + "\">" + ifo + "</a>")
  file.write("  </td>")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  file.write("</tbody>\n</table><br>\n\n")


  # Write parameter estimation table
  file.write("<h3>Parameter estimation</h3>\n<table style=\"text-align: left; height: 259px; width: 100%;\" border=\"1\" cellpadding=\"2\" cellspacing=\"2\">\n\n<tbody>\n")

  file.write("<tr>\n")
  file.write("  <td>ID</td>\n")
  file.write("  <td>Questions</td>\n")
  file.write("  <td>Answers</td>\n")
  file.write("  <td>Relevant information (flags, plots and links)</td>\n")
  file.write("  <td>Comments</td>\n")
  file.write("</tr>\n\n")

  # Row #1
  file.write("<tr>\n")
  file.write("  <td>#1 Parameters of the candidate</td>\n")
  file.write("  <td>Can we get more accurate information on the parameters of this candidate using MCMC or Bayesian methods ?</td>\n")
  file.write("  <td></td>\n")
  file.write("  <td>MCMC results:</td>\n")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #2
  file.write("<tr>\n")
  file.write("  <td>#2 Coherent follow-up</td>\n")
  file.write("  <td>Make a followup with coherent multi-detector code.</td>\n")
  file.write("  <td></td>\n")
  file.write("  <td></td>\n")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #3
  file.write("<tr>\n")
  file.write("  <td>#3</td>\n")
  file.write("  <td>Are the results of the Burst analysis astrophysically consistent with a possible detection ?</td>\n")
  file.write("  <td></td>\n")
  file.write("  <td></td>\n")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #4
  file.write("<tr>\n")
  file.write("  <td>#4</td>\n")
  file.write("  <td>Are the results of a ringdown search astrophisycally consistent with a possible detection ?</td>\n")
  file.write("  <td></td>\n")
  file.write("  <td></td>\n")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  # Row #5
  file.write("<tr>\n")
  file.write("  <td>#5 EM triggers</td>\n")
  file.write("  <td>Are there any EM triggers in coincidence with the candidate ?<br>Is the distance estimated from interferometer time-delays or coherent analysis consistent with electro-magnetic observations?<br>? Are the distances as measured in several instruments consistent with position information?<br></td>\n")
  file.write("  <td></td>\n")
  file.write("  <td><a href=\"http://www.uoregon.edu/~ileonor/ligo/s5/grb/online/S5grbs_list.html\">List of GRBs during S5</a><br><a href=\"http://ldas-jobs.ligo.caltech.edu/~dietz/pages/s5/GRB/CVS/overviewS5.html\">CBC compiled list of GRBs</a></td>\n")
  file.write("  <td></td>\n")
  file.write("</tr>\n\n")

  file.write("</tbody>\n</table>\n\n</body>\n</html>")

  file.close()

