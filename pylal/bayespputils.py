#       bayespputils.py
#
#       Copyright 2010 Benjamin Aylott <benjamin.aylott@ligo.org>, John Veitch <john.veitch@ligo.org>
#
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 2 of the License, or
#       (at your option) any later version.
#
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.

#===============================================================================
# Preamble
#===============================================================================

"""
This module contains classes and functions for post-processing the output
of the Bayesian parameter estimation codes.
"""

#standard library imports
import os
from math import ceil,floor,sqrt
import xml
from xml.dom import minidom

#related third party imports
import numpy as np
from matplotlib import pyplot as plt,cm as mpl_cm

try:
    from xml.etree.cElementTree import Element, SubElement, ElementTree, Comment, tostring, XMLParser
except ImportError:
    #Python < 2.5
    from cElementTree import Element, SubElement, ElementTree, Comment, tostring, XMLParser

#local application/library specific imports
import pylal
from pylal import git_version

from _bayespputils import _skyhist_cart,_calculate_confidence_levels

__author__="Ben Aylott <benjamin.aylott@ligo.org>, John Veitch <john.veitch@ligo.org>"
__version__= "git id %s"%git_version.id
__date__= git_version.date

#===============================================================================
# Class definitions
#===============================================================================

class OneDPosterior(object):
    def __init__(self,name,posterior_samples,injected_value=None,prior=None):
        self.__name=name
        self.__posterior_samples=np.array(posterior_samples)

        if injected_value is not None:
            self.__injval=injected_value
        else:
            self.__injval=None

        if prior is not None and type(prior)==type(function):
            self.__prior=prior
        else:
            self.__prior=None

        return

    @property
    def mean(self):
        return np.mean(self.__posterior_samples)

    @property
    def median(self):
        return np.median(self.__posterior_samples)

    @property
    def stdev(self):
        return sqrt(np.var(self.__posterior_samples))

    @property
    def stacc(self):
        if self.__injval is None:
            return None
        else:
            return sqrt(np.var(self.__posterior_samples)+pow((np.mean(self.__posterior_samples)-self.__injval),2) )

    @property
    def injval(self):
        return self.__injval

    @property
    def samples(self):
        return self.__posterior_samples

    @property
    def gaussian_kde(self):
        from scipy import stats
        from scipy import seterr as sp_seterr

        sp_seterr(under='ignore')

        return stats.kde.gaussian_kde(self.__posterior_samples)

class Posterior(object):

    def __init__(self,commonOutputTableFileObj,SimInspiralTableEntry=None):
        """
        Constructor.
        """
        common_output_table_header,common_output_table_raw =\
            self._load_posterior_table_from_data_file(commonOutputTableFileObj)
        self._posterior={}
        self._injection=SimInspiralTableEntry
        for one_d_posterior_samples,param_name in zip(np.hsplit(common_output_table_raw,common_output_table_raw.shape[1]),common_output_table_header):
            param_name=param_name.lower()
            self._posterior[param_name]=OneDPosterior(param_name.lower(),one_d_posterior_samples,injected_value=self._getinjpar(param_name))
        self._logL=np.array(common_output_table_raw[:,-1])

        return

    def _inj_m1(inj):
        (mass1,mass2)=masses
        return mass1
    def _inj_m2(inj):
        (mass1,mass2)=masses
        return mass2

    def _inj_mchirp(inj):
        return inj.mchirp

    def _inj_eta(inj):
        return inj.eta

    _injXMLFuncMap={
                        'mchirp':lambda inj:inj.mchirp,
                        'mc':lambda inj:inj.mchirp,
                        'mass1':_inj_m1,
                        'm1':_inj_m1,
                        'mass2':_inj_m2,
                        'm2':_inj_m2,
                        'eta':lambda inj:inj.eta,
                        'time': lambda inj:float(inj.get_end()),
                        'end_time': lambda inj:float(inj.get_end()),
                        'phi0':lambda inj:inj.phi0,
                        'dist':lambda inj:inj.distance,
                        'distance':lambda inj:inj.distance,
                        'ra':lambda inj:inj.longitude,
                        'long':lambda inj:inj.longitude,
                        'longitude':lambda inj:inj.longitude,
                        'dec':lambda inj:inj.latitude,
                        'lat':lambda inj:inj.latitude,
                        'latitude':lambda inj:inj.latitude,
                        'psi': lambda inj: inj.polarization,
                        'iota':lambda inj: inj.inclination,
                        'inclination': lambda inj: inj.inclination,
                       }

    def _getinjpar(self,paramname):
        if self._injection is not None:
            for key,value in self._injXMLFuncMap.items():
                if paramname in key:
                    return self._injXMLFuncMap[key](self._injection)
        return None


    def __getitem__(self,key):
        """
        Returns posterior chain,one_d_pos, with name one_d_pos.name.
        """
        return self._posterior[key.lower()]

    def __len__(self):
        """
        Defined as number of samples.
        """
        return len(self._logL)

    def __iter__(self):
        """
        Returns iterator from self.forward for us in for (...) in (...) .
        """
        return self.forward()

    def forward(self):
        """
        Forward iterator (in sense of over list of names) over Posterior
        with name,one_d_pos.
        """
        current_item = 0
        while current_item < self.dim:
            name=self._posterior.keys()[current_item]
            pos=self._posterior[name]
            current_item += 1
            yield name,pos

    @property
    def dim(self):
        """
        Defined as number of parameters.
        """
        return len(self._posterior.keys())

    @property
    def names(self):
        """
        Return list of parameter names.
        """
        nameslist=[]
        for key,value in self:
            nameslist.append(key)
        return nameslist

    @property
    def means(self):
        """
        Return dict {paramName:paramMean} .
        """
        meansdict={}
        for name,pos in self:
            meansdict[name]=pos.mean
        return meansdict

    @property
    def medians(self):
        """
        Return dict {paramName:paramMedian} .
        """
        mediansdict={}
        for name,pos in self:
            mediansdict[name]=pos.median
        return mediansdict

    def _load_posterior_table_from_data_file(self,infile):
        """
        Parses a file and return an array of posterior samples and list of
        parameter names. Will apply inverse function to columns with names
        containing sin,cos,log.
        """
        #infile=open(filename,'r')
        formatstr=infile.readline().lstrip()
        formatstr=formatstr.replace('#','')
        header=formatstr.split()

        llines=[]
        import re
        dec=re.compile(r'[^Ee+\d.-]+')
        line_count=0
        for line in infile:
            sline=line.split()
            proceed=True
            if len(sline)<1:
                print 'Ignoring empty line in input file: %s'%(sline)
                proceed=False
            for s in sline:
                if dec.search(s) is not None:
                    print 'Warning! Ignoring non-numeric data after the header: %s'%(sline)
                    proceed=False
            if proceed:
                llines.append(np.array(map(float,sline)))
        flines=np.array(llines)
        for i in range(0,len(header)):
            if header[i].lower().find('log')!=-1 and header[i].lower()!='logl':
                print 'exponentiating %s'%(header[i])
                flines[:,i]=np.exp(flines[:,i])
                header[i]=header[i].replace('log','')
            if header[i].lower().find('sin')!=-1:
                print 'asining %s'%(header[i])
                flines[:,i]=np.arcsin(flines[:,i])
                header[i]=header[i].replace('sin','')
            if header[i].lower().find('cos')!=-1:
                print 'acosing %s'%(header[i])
                flines[:,i]=np.arccos(flines[:,i])
                header[i]=header[i].replace('cos','')
            header[i]=header[i].replace('(','')
            header[i]=header[i].replace(')','')
        print 'Read columns %s'%(str(header))
        return header,flines

    def append(self,one_d_posterior):
        """
        Container method. Add a new OneDParameter to the Posterior instance.
        """
        self._posterior[one_d_posterior.name]=one_d_posterior
        return

    def _posMode(self):
        """
        Find the sample with maximum posterior probability.
        """
        pos_vals=self._logL
        max_i=0
        max_pos=pos_vals[0]
        for i in range(len(pos_vals)):
            if pos_vals[i] > max_pos:
                max_pos=pos_vals[i]
                max_i=i
        return max_pos,max_i

    def _print_table_row(self,name,entries):
        """
        Print a html table row representation of

        name:item1,item2,item3,...
        """

        row_str='<tr><td>%s</td>'%name
        for entry in entries:
            row_str+='<td>%s</td>'%entry
        row_str+='</tr>'
        return row_str

    @property
    def maxL(self):
        """
        Return the maximum posterior probability and the corresponding
        set of parameters.
        """
        maxLvals={}
        max_pos,max_i=self._posMode()
        for param_name in self.names:
            maxLvals[param_name]=self._posterior[param_name].samples[max_i][0]

        return (max_pos,maxLvals)

    def write_to_file(self,fname):
        """
        Dump the posterior table to a file in the agreed format.
        """
        column_list=()
        header_string=''
        posterior_table=[]
        for param_name,one_pos in self:
            column=np.array(one_pos.samples)
            header_string+=param_name+' '
            posterior_table.append(column)
        posterior_table=tuple(posterior_table)
        posterior_table=np.column_stack(posterior_table)
        fobj=open(fname,'w')

        fobj.write(header_string+'\n')
        np.savetxt(fobj,posterior_table)
        fobj.close()

        return

    def __str__(self):
        """
        Define a string representation of the Posterior class ; returns
        a html formatted table of various properties of posteriors.
        """
        return_val='<table border="1" width="100%"><tr><th/>'

        column_names=['maxL','stdev','mean','median','stacc','injection value']
        for column_name in column_names:
            return_val+='<th>%s</th>'%column_name

        return_val+='</tr>'

        for name,oned_pos in self:

            max_pos,max_i=self._posMode()
            maxL=oned_pos.samples[max_i][0]
            mean=str(oned_pos.mean)
            stdev=str(oned_pos.stdev)
            median=str(oned_pos.median)
            stacc=str(oned_pos.stacc)
            injval=str(oned_pos.injval)

            return_val+=self._print_table_row(name,[maxL,stdev,mean,median,stacc,injval])

        return_val+='</table>'

        parser=XMLParser()
        parser.feed(return_val)
        Estr=parser.close()

        elem=Estr
        rough_string = tostring(elem, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        return_val=reparsed.toprettyxml(indent="  ")

        return return_val

#===============================================================================
# Internal module functions
#===============================================================================

def _skyhist_cart_slow(skycarts,sky_samples):
    """
    @deprecated: This is a pure python version of the C extension function
        pylal._bayespputils._skyhist_cart .
    """

    N=len(skycarts)
    print 'operating on %d sky points'%(N)
    bins=np.zeros(N)
    for RAsample,decsample in sky_samples:
        sampcart=pol2cart(RAsample,decsample)
        maxdx=-1
        maxvalue=-1
        for i in xrange(0,N):
            dx=np.dot(sampcart,skycarts[i])
            if dx>maxvalue:
                    maxdx=i
                    maxvalue=dx

        bins[maxdx]+=1
    return bins
#
def _sky_hist(skypoints,samples):
    """
    @deprecated: This is an old pure python version of the C extension function
        pylal._bayespputils._skyhist_cart .
    """
    N=len(skypoints)
    print 'operating on %d sky points' % (N)
    bins=zeros(N)
    j=0
    for sample in samples:
        seps=map(lambda s: ang_dist(sample[RAdim],sample[decdim],s[1],s[0]),skypoints)
        minsep=math.pi
        for i in range(0,N):
            if seps[i]<minsep:
                minsep=seps[i]
                mindx=i
        bins[mindx]=bins[mindx]+1
        j=j+1
        print 'Done %d/%d iterations, minsep=%f degrees'\
            %(j,len(samples),minsep*(180.0/3.1415926))
    return (skypoints,bins)
#

def _calculate_sky_confidence_slow(
                                shist,
                                skypoints,
                                injbin,
                                skyres_,
                                confidence_levels,
                                lenpos):
    """
    @deprecated: This is a pure python version of the C extension function
        pylal._bayespputils._calculate_confidence_levels.
    """
    frac=0
    Nbins=0
    injectionconfidence=None
    #print "lenpos : %i"%lenpos
    #toppoints=[(None,None,None)]*lenpos
    toppoints=[]

    skyreses=[]
    lenbins=len(shist)
    range_lenbins=range(0,lenbins)
    for confidence_level in confidence_levels:
        while(frac<confidence_level):
            maxbin=0
            for i in range_lenbins:
                if shist[i]>maxbin:
                    maxbin=shist[i]
                    maxpos=i

            shist[maxpos]=0
            frac=frac+(float(maxbin)/(lenpos))

            Nbins=Nbins+1
            toppoints.append((skypoints[maxpos,0],skypoints[maxpos,1],maxpos,frac))
            if injbin is not None:
                if (injbin==maxpos):
                    injectionconfidence=frac
                    print 'Injection sky point found at confidence %f'%(frac)

        print '%f confidence region: %f square degrees' % (frac,Nbins*float(skyres_)*float(skyres_))
        skyreses.append((frac,Nbins*float(skyres_)*float(skyres_)))
        toppoints=toppoints[:Nbins]
    return injectionconfidence,toppoints,skyreses

def _histN(mat,N):
    """
    @deprecated: UNUSED .
    """
    Nd=size(N)
    histo=zeros(N)
    scale=array(map(lambda a,b:a/b,map(lambda a,b:(1*a)-b,map(max,mat),map(min,mat)),N))
    axes=array(map(lambda a,N:linspace(min(a),max(a),N),mat,N))
    bins=floor(map(lambda a,b:a/b , map(lambda a,b:a-b, mat, map(min,mat) ),scale*1.01))

    hbins=reshape(map(int,bins.flat),bins.shape)
    for co in transpose(hbins):
        t=tuple(co)
        histo[t[::-1]]=histo[t[::-1]]+1
    return (axes,histo)
#

def _greedy_bin(greedyHist,greedyPoints,injection_bin_index,bin_size,Nsamples,confidence_levels):
    """
    An interal function representing the common, dimensionally-independent part of the
    greedy binning algorithms.
    """

    #Now call confidence level C extension function to determine top-ranked pixels
    (injectionconfidence,toppoints)=_calculate_confidence_levels(
                                                                    greedyHist,
                                                                    greedyPoints,
                                                                    injection_bin_index,
                                                                    bin_size,
                                                                    Nsamples
                                                                    )

    #Determine interval/area contained within given confidence intervals
    nBins=0
    confidence_levels.sort()
    reses={}
    toppoints=np.array(toppoints)
    for printcl in confidence_levels:
        nBins=1
        #Start at top of list of ranked pixels...
        accl=toppoints[0,3]

        #Loop over next significant pixels and their confidence levels

        while accl<printcl and nBins<=len(toppoints):
            nBins=nBins+1
            accl=toppoints[nBins-1,3]

        reses[printcl]=nBins*bin_size

    #Find area
    injection_area=None
    if injection_bin_index and injectionconfidence:
        i=list(np.nonzero(np.asarray(toppoints)[:,2]==injection_bin_index))[0]
        injection_area=bin_size*i

    return toppoints,injectionconfidence,reses,injection_area
#


#
#===============================================================================
# Public module functions
#===============================================================================

def greedy_bin_two_param(posterior,greedy2Params,confidence_levels):
    """
    Determine the 2-parameter Bayesian Confidence Intervals using a greedy
        binning algorithm.

    @param posterior: an instance of the Posterior class.
    @param greedy2Params: a dict ;{param1Name:param1binSize,param2Name:param2binSize}
    @param confidence_levels: A list of floats of the required confidence intervals [(0-1)].
    """

    #Extract parameter names
    par1_name,par2_name=greedy2Params.keys()

    #Set posterior array columns
    par1pos=posterior[par1_name.lower()].samples
    par2pos=posterior[par2_name.lower()].samples

    #Extract bin sizes
    par1_bin=greedy2Params[par1_name]
    par2_bin=greedy2Params[par2_name]

    #Extract injection information
    par1_injvalue=posterior[par1_name.lower()].injval
    par2_injvalue=posterior[par2_name.lower()].injval

    #Create 2D bin array
    par1pos_min=min(par1pos)[0]
    par2pos_min=min(par2pos)[0]

    par1pos_max=max(par1pos)[0]
    par2pos_max=max(par2pos)[0]

    par1pos_Nbins= int(ceil((par1pos_max - par1pos_min)/par1_bin))+1

    par2pos_Nbins= int(ceil((par2pos_max - par2pos_min)/par2_bin))+1

    greedyHist = np.zeros(par1pos_Nbins*par2pos_Nbins,dtype='i8')
    greedyPoints = np.zeros((par1pos_Nbins*par2pos_Nbins,2))

    #Fill bin values
    par1_point=par1pos_min
    par2_point=par2pos_min
    for i in range(par2pos_Nbins):

        par1_point=par1pos_min
        for j in range(par1pos_Nbins):

            greedyPoints[j+par1pos_Nbins*i,0]=par1_point
            greedyPoints[j+par1pos_Nbins*i,1]=par2_point
            par1_point+=par1_bin
        par2_point+=par2_bin


    #If injection point given find which bin its in...
    injbin=None
    if par1_injvalue is not None and par2_injvalue is not None:

        par1_binNumber=int(floor((par1_injvalue-par1pos_min)/par1_bin))
        par2_binNumber=int(floor((par2_injvalue-par2pos_min)/par2_bin))

        injbin=int(par1_binNumber+par2_binNumber*par1pos_Nbins)
    elif par1_injvalue is None and par2_injvalue is not None:
        print "Injection value not found for %s!"%par1_name

    elif par1_injvalue is not None and par2_injvalue is None:
        print "Injection value not found for %s!"%par2_name

    #Bin posterior samples
    for par1_samp,par2_samp in zip(par1pos,par2pos):
        par1_samp=par1_samp[0]
        par2_samp=par2_samp[0]
        par1_binNumber=int(floor((par1_samp-par1pos_min)/par1_bin))
        par2_binNumber=int(floor((par2_samp-par2pos_min)/par2_bin))
        try:
            greedyHist[par1_binNumber+par2_binNumber*par1pos_Nbins]+=1
        except:
            print par1_binNumber,par2_binNumber,par1pos_Nbins,par2pos_Nbins,par1_binNumber+par2_binNumber*par1pos_Nbins,par1_samp,par1pos_min,par1_bin,par1_samp,par2pos_min,par2_bin
            exit(1)
    toppoints,injection_cl,reses,injection_area=\
                                _greedy_bin(
                                                greedyHist,
                                                greedyPoints,
                                                injbin,
                                                float(sqrt(par1_bin*par2_bin)),
                                                int(len(par1pos)),
                                                confidence_levels
                                            )

    return toppoints,injection_cl,reses,injection_area

def pol2cart(long,lat):
    """
    Utility function to convert longitude,latitude on a unit sphere to
        cartesian co-ordinates.
    """

    x=np.cos(lat)*np.cos(long)
    y=np.cos(lat)*np.sin(long)
    z=np.sin(lat)
    return np.array([x,y,z])
#


def greedy_bin_sky(posterior,skyres,confidence_levels):
    """
    Greedy bins the sky posterior samples into a grid on the sky constructed so that
    sky boxes have roughly equal size (determined by skyres).

    @param posterior: Posterior class instance containing ra and dec samples.

    @param skyres: Desired approximate size of sky pixel on one side.

    @param confidence_levels: List of desired confidence levels [(0-1)].
    """

    from pylal import skylocutils

    np.seterr(under='ignore')

    skypos=np.column_stack([posterior['ra'].samples,posterior['dec'].samples])

    injvalues=None

    sky_injpoint=(posterior['ra'].injval,posterior['dec'].injval)

    skypoints=np.array(skylocutils.gridsky(float(skyres)))
    skycarts=map(lambda s: pol2cart(s[1],s[0]),skypoints)
    skyinjectionconfidence=None

    shist=_skyhist_cart(np.array(skycarts),skypos)

    #shist=skyhist_cart(skycarts,list(pos))
    bins=skycarts

    # Find the bin of the injection if available
    injbin=None
    if None not in sky_injpoint:
        injhist=_skyhist_cart_slow(skycarts,np.array([sky_injpoint]))
        injbin=injhist.tolist().index(1)
        print 'Found injection in bin %d with co-ordinates %f,%f .'%(
                                                                     injbin,
                                                                     skypoints[injbin,0],
                                                                     skypoints[injbin,1]
                                                                     )

    return _greedy_bin(shist,skypoints,injbin,float(skyres),len(skypos),confidence_levels)


def plot_sky_map(top_ranked_pixels,outdir):
    """
    Plots a sky map using the Mollweide projection in the Basemap package.

    @param top_ranled_pixels: the top-ranked sky pixels as determined by greedy_bin_sky.

    @param outdir: Output directory in which to save skymap.png image.
    """
    from mpl_toolkits.basemap import Basemap
    from pylal import skylocutils

    np.seterr(under='ignore')

    myfig=plt.figure()
    plt.clf()
    m=Basemap(projection='moll',lon_0=180.0,lat_0=0.0)
    plx,ply=m(
              np.asarray(top_ranked_pixels)[::-1,1]*57.296,
              np.asarray(top_ranked_pixels)[::-1,0]*57.296
              )

    cnlevel=[1-tp for tp in np.asarray(top_ranked_pixels)[::-1,3]]
    plt.scatter(plx,ply,s=5,c=cnlevel,faceted=False,cmap=mpl_cm.jet)
    m.drawmapboundary()
    m.drawparallels(np.arange(-90.,120.,45.),labels=[1,0,0,0],labelstyle='+/-')
    # draw parallels
    m.drawmeridians(np.arange(0.,360.,90.),labels=[0,0,0,1],labelstyle='+/-')
    # draw meridians
    plt.title("Skymap") # add a title
    plt.colorbar()
    myfig.savefig(os.path.join(outdir,'skymap.png'))
    plt.clf()

    #Save skypoints
    np.savetxt(
               os.path.join(outdir,'ranked_sky_pixels.dat'),
               np.column_stack(
                               [
                                np.asarray(top_ranked_pixels)[:,0:1],
                                np.asarray(top_ranked_pixels)[:,1],
                                np.asarray(top_ranked_pixels)[:,3]
                                ]
                               )
               )

    return myfig
#

def plot_two_param_greedy_bins(toppoints,posterior,greedy2Params):
    """
    Plots the top-ranked pixels by confidence level produced by the 2-parameter
    greedy binning algorithm.

    @param toppoints: Nx2 array of 2-parameter posterior samples.

    @param posterior: an instance of the Posterior class.

    @param greedy2Params: a dict ;{param1Name:param1binSize,param2Name:param2binSize}
    """

    #Extract parameter names
    par1_name,par2_name=greedy2Params.keys()

    #Extract bin sizes
    par1_bin=greedy2Params[par1_name]
    par2_bin=greedy2Params[par2_name]

    #Extract injection information
    par1_injvalue=posterior[par1_name.lower()].injval
    par2_injvalue=posterior[par2_name.lower()].injval

    #Work out good bin size
    xbins=int(ceil((max(toppoints[:,0])-min(toppoints[:,0]))/par1_bin))
    ybins=int(ceil((max(toppoints[:,1])-min(toppoints[:,1]))/par2_bin))

    if xbins==0:
        xbins=1
    if ybins==0:
        ybins=1

    _dpi=120
    xsize_in_inches=6.
    xsize_points = xsize_in_inches * _dpi

    points_per_bin_width=xsize_points/xbins

    ysize_points=ybins*points_per_bin_width
    ysize_in_inches=ysize_points/_dpi
    #
    myfig=plt.figure(1,figsize=(xsize_in_inches+2,ysize_in_inches+2),dpi=_dpi)

    cnlevel=[1-tp for tp in toppoints[:,3]]
    #
    coll=myfig.gca().scatter(
                             toppoints[:,0],
                             toppoints[:,1],
                             s=int(points_per_bin_width*1.5),
                             faceted=False,
                             marker='s',
                             c=cnlevel,
                             cmap=mpl_cm.jet
                             )

    plt.colorbar(mappable=coll,ax=myfig.gca(),cax=myfig.gca())

    #Determine limits based on injection point (if any) and min/max values

    min_xlim=min(toppoints[:,0])
    max_xlim=max(toppoints[:,0])

    min_ylim=min(toppoints[:,1])
    max_ylim=max(toppoints[:,1])

    if par1_injvalue is not None and par2_injvalue is not None:
        myfig.gca().plot([par1_injvalue],[par2_injvalue],'r*',ms=20.)

        if par1_injvalue < min(toppoints[:,0]):
            min_xlim=par1_injvalue
        elif par1_injvalue > max(toppoints[:,0]):
            max_xlim=par1_injvalue

        if par2_injvalue < min(toppoints[:,1]):
            min_ylim=par2_injvalue
        elif par2_injvalue > max(toppoints[:,1]):
            max_ylim=par2_injvalue
#
    #Set limits on axes determined above
    myfig.gca().set_xlim(min_xlim,max_xlim)
    myfig.gca().set_ylim(min_ylim,max_ylim)

    #Reset figure size (above probably had no effect apart from to give correct bin sizes)
    myfig.set_figheight(6)
    myfig.set_figwidth(6)
    plt.title("%s-%s histogram (greedy binning)"%(par1_name,par2_name)) # add a title

    return myfig
#

def mc2ms(mc,eta):
    """
    Utility function for converting mchirp,eta to component masses.
    """
    root = np.sqrt(0.25-eta)
    fraction = (0.5+root) / (0.5-root)
    invfraction = 1/fraction

    m1= mc * np.power((1+fraction),0.2) / np.power(fraction,0.6)

    m2= mc* np.power(1+invfraction,0.2) / np.power(invfraction,0.6)
    return (m1,m2)
#
#
def ang_dist(long1,lat1,long2,lat2):
    """
    Find the angular separation of (long1,lat1) and (long2,lat2), which are
        specified in radians.
    """

    x1=np.cos(lat1)*np.cos(long1)
    y1=np.cos(lat1)*np.sin(long1)
    z1=np.sin(lat1)
    x2=np.cos(lat2)*np.cos(long2)
    y2=np.cos(lat2)*np.sin(long2)
    z2=np.sin(lat2)
    sep=math.acos(x1*x2+y1*y2+z1*z2)
    return(sep)

#

def plot_one_param_pdf(posterior,plot1DParams):
    """
    Plots a 1D histogram and (gaussian) kernel density estimate of the
    distribution of posterior samples for a given parameter.

    @param posterior: an instance of the Posterior class.

    @param plot1DParams: a dict; {paramName:Nbins}

    """

    from scipy import stats
    from scipy import seterr as sp_seterr

    param=plot1DParams.keys()[0].lower()
    histbins=plot1DParams.values()[0]

    pos_samps=posterior[param].samples
    injpar=posterior[param].injval

    myfig=plt.figure(figsize=(4,3.5),dpi=80)

    (n, bins, patches)=plt.hist(pos_samps,histbins,normed='true')
    histbinSize=bins[1]-bins[0]

    np.seterr(under='ignore')
    sp_seterr(under='ignore')

    pos_sampsT=np.transpose(pos_samps)

    try:
        gkde=stats.kde.gaussian_kde(pos_sampsT)
    except np.linalg.linalg.LinAlgError:
        print "Error occured generating plot for parameter %s: %s !\
                Trying next parameter."%(param,'LinAlgError')
        return

    ind=np.linspace(np.min(pos_samps),np.max(pos_samps),101)
    kdepdf=gkde.evaluate(ind)
    plt.plot(ind,kdepdf,label='density estimate')

    rbins=None

    if injpar:
        if min(pos_samps)<injpar and max(pos_samps)>injpar:
            plt.plot([injpar,injpar],[0,max(kdepdf)],'r-.',scalex=False,scaley=False)

            #rkde=gkde.integrate_box_1d(min(pos[:,i]),getinjpar(injection,i))
            #print "r of injected value of %s (kde) = %f"%(param,rkde)

            #Find which bin the true value is in
            bins_to_inj=(injpar-bins[0])/histbinSize
            injbinh=int(floor(bins_to_inj))
            injbin_frac=bins_to_inj-float(injbinh)

            #Integrate over the bins
            rbins=(sum(n[0:injbinh-1])+injbin_frac*n[injbinh])*histbinSize

    #
    plt.grid()
    plt.xlabel(param)
    plt.ylabel('Probability Density')

    return rbins,myfig#,rkde
#

def plot_two_param_kde(posterior,plot2DkdeParams):
    """xdat,ydat,Nx,Ny,par_names=None,par_injvalues=None
    Plots a 2D kernel density estimate of the 2-parameter marginal posterior.

    @param posterior: an instance of the Posterior class.

    @param plot2DkdeParams: a dict {param1Name:Nparam1Bins,param2Name:Nparam2Bins}
    """

    from scipy import seterr as sp_seterr
    from scipy import stats

    from matplotlib import pyplot as plt

    par1_name,par2_name=plot2DkdeParams.keys()
    Nx=plot2DkdeParams[par1_name]
    Ny=plot2DkdeParams[par2_name]

    xdat=posterior[par1_name].samples
    ydat=posterior[par2_name].samples

    par_injvalue1=posterior[par1_name].injval
    par_injvalue2=posterior[par2_name].injval

    np.seterr(under='ignore')
    sp_seterr(under='ignore')

    myfig=plt.figure(1,figsize=(6,4),dpi=80)
    plt.clf()

    xax=np.linspace(min(xdat),max(xdat),Nx)
    yax=np.linspace(min(ydat),max(ydat),Ny)
    x,y=np.meshgrid(xax,yax)

    samp=np.transpose(np.column_stack((xdat,ydat)))

    kde=stats.kde.gaussian_kde(samp)
    grid_coords = np.append(x.reshape(-1,1),y.reshape(-1,1),axis=1)

    z = kde(grid_coords.T)
    z = z.reshape(Nx,Ny)
    asp=xax.ptp()/yax.ptp()
#    if(asp<0.8 or asp > 1.6): asp=1.4
    plt.imshow(z,extent=(xax[0],xax[-1],yax[0],yax[-1]),aspect=asp,origin='lower')
    plt.colorbar()

    if par_injvalue1 is not None and par_injvalue2 is not None:
        plt.plot([par_injvalue1],[par_injvalue2],'go',scalex=False,scaley=False)

    plt.xlabel(par1_name)
    plt.ylabel(par2_name)
    plt.grid()

    return myfig
#



def stacc_stat(posterior,name):
    """
    Ilya's 'standard accuracy statistic - a standard deviant incorporating
    information about the accuracy of the waveform recovery.

    @param posterior: an instance of the Posterior class.

    @param name: the literal name of the parameter
    """

    return posterior[name].stacc()
#

def greedy_bin_one_param(posterior,greedy1Param,confidence_levels):
    """
    Determine the 1-parameter Bayesian Confidence Interval using a greedy
    binning algorithm.

    @param posterior: an instance of the posterior class.

    @param greedy1Param: a dict; {paramName:paramBinSize}.

    @param confidence_levels: A list of floats of the required confidence intervals [(0-1)].
    """

    paramName=greedy1Param.keys()[0]
    par_bin=greedy1Param.values()[0]
    par_samps=posterior[paramName.lower()].samples

    parpos_min=min(par_samps)[0]
    parpos_max=max(par_samps)[0]

    par_point=parpos_min

    parpos_Nbins= int(ceil((parpos_max - parpos_min)/par_bin))+1

    greedyPoints=np.zeros((parpos_Nbins,2))
    # ...NB 2D so it can be put through same confidence level function
    greedyHist=np.zeros(parpos_Nbins,dtype='i8')

    #Bin up
    for i in range(parpos_Nbins):
        greedyPoints[i,0]=par_point
        greedyPoints[i,1]=par_point
        par_point+=par_bin

    for par_samp in par_samps:
        par_samp=par_samp[0]
        par_binNumber=int(floor((par_samp-parpos_min)/par_bin))
        try:
            greedyHist[par_binNumber]+=1
        except IndexError:
            print "IndexError: bin number: %i total bins: %i parsamp: %f "\
                %(par_binNumber,parpos_Nbins,par_samp)

    #Find injection bin
    injbin=None
    par_injvalue=posterior[paramName].injval
    if par_injvalue:
        par_binNumber=floor((par_injvalue-parpos_min)/par_bin)
        injbin=par_binNumber

    gbOut=_greedy_bin(greedyHist,greedyPoints,injbin,float(sqrt(par_bin*par_bin)),int(len(par_samps)),confidence_levels)

    return gbOut

#
def contigious_interval_one_param(posterior,contInt1Params,confidence_levels):
    """
    Calculates the smallest contigious 1-parameter confidence interval for a
    set of given confidence levels.

    @param posterior: an instance of the Posterior class.

    @param contInt1Params: a dict {paramName:paramBinSize}.

    @param confidence_levels: Required confidence intervals.

    """
    oneDContCL={}
    oneDContInj={}

    paramName=contInt1Params.keys()[0]
    par_bin=contInt1Params.values()[0]

    par_injvalue=posterior[paramName].injval

    par_samps=posterior[paramName].samples

    parpos_min=min(par_samps)
    parpos_max=max(par_samps)

    par_point=parpos_min
    parpos_Nbins= int(ceil((parpos_max - parpos_min)/par_bin))+1

    greedyHist=np.zeros(parpos_Nbins,dtype='i8')

    for par_samp in par_samps:
        par_binNumber=int(floor((par_samp-parpos_min)/par_bin))
        try:
            greedyHist[par_binNumber]+=1
        except IndexError:
            print "IndexError: bin number: %i total bins: %i parsamp: %f bin: %f - %f"\
                %(
                  par_binNumber,
                  parpos_Nbins,
                  par_samp,
                  greedyPoints[par_binNumber-1,0],
                  greedyPoints[par_binNumber-1,0]+par_bin
                  )

    injbin=None
    #Find injection bin
    if par_injvalue:
        par_binNumber=floor((par_injvalue-parpos_min)/par_bin)
        injbin=par_binNumber

    j=0
    #print "Calculating contigious confidence intervals for %s..."%par_name
    len_par_samps=len(par_samps)

    injinterval=None

    #Determine smallest contigious interval for given confidence levels (brute force)
    while j < len(confidence_levels):
        confidence_level=confidence_levels[j]
        #Loop over size of interval
        max_left=0
        max_right=0

        for i in range(len(greedyHist)):

            max_frac=None
            left=0
            right=i

            #Slide interval
            while right<len(greedyHist):
                Npoints=sum(greedyHist[left:right])
                frac=float(Npoints)/float(len_par_samps)
                #print "left %i , right %i , frac %f"%(left,right,frac)

                if max_frac is None:
                    max_frac=frac
                    max_left=left
                    max_right=right
                else:
                    if frac>max_frac:
                        max_frac=frac
                        max_left=left
                        max_right=right

                left+=1
                right+=1

            if injbin is not None and injinterval is None:
                if injbin in range(max_left,max_right):
                    injinterval=(max_right-max_left)*par_bin
                    oneDContInj['interval']=injinterval
                    oneDContInj['confidence']=1-frac
            if max_frac > confidence_level:
                break

            max_frac=None

        if max_frac is None:
            print "Cant determine intervals at %f confidence!"%confidence_level
        else:

            oneDContCL['left']=max_left*par_bin
            oneDContCL['right']=max_right*par_bin
            oneDContCL['width']=(max_right-max_left)*par_bin
            k=j
            while k+1<len(confidence_levels) :
                if confidence_levels[k+1]<max_frac:
                    j+=1
                k+=1
        j+=1

    return oneDContCL,oneDContInj
#

############################
#Webpage stuff
############################

class htmlChunk(object):

    def __init__(self,tag,attrib=None,parent=None):

        self._html=Element(tag)#attrib={'xmlns':"http://www.w3.org/1999/xhtml"})
        if attrib:
            for attribname,attribvalue in attrib.items():
                self._html.attrib[attribname]=attribvalue
        if parent:
            parent.append(self._html)


    def toprettyxml(self):
        """
        Return a pretty-printed XML string of the htmlPage.
        """
        elem=self._html
        rough_string = tostring(elem)
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")

    def __str__(self):
        return self.toprettyxml()

    def write(self,string):
        parser=XMLParser()
        parser.feed(string)
        Estr=parser.close()
        self._html.append(Estr)

    def p(self,pstring):
        Ep=Element('p')
        Ep.text=pstring
        self._html.append(Ep)
        return Ep

    def h1(self,h1string):
        Ep=Element('h1')
        Ep.text=h1string
        self._html.append(Ep)
        return Ep
#
    def h5(self,h1string):
        Ep=Element('h5')
        Ep.text=h1string
        self._html.append(Ep)
        return Ep

    def h3(self,h1string):
        Ep=Element('h3')
        Ep.text=h1string
        self._html.append(Ep)
        return Ep

    def br(self):
        Ebr=Element('br')
        self._html.append(Ebr)
        return Ebr

    def hr(self):
        Ehr=Element('hr')
        self._html.append(Ehr)
        return Ehr

    def a(self,url,linktext):
        Ea=Element('a')
        Ea.attrib['href']=url
        Ea.text=linktext
        self._html.append(Ea)
        return Ea

    def append(self,element):
        self._html.append(element)


#
class htmlPage(htmlChunk):

    def __init__(self,title=None):
        htmlChunk.__init__(self,'html',attrib={'xmlns':"http://www.w3.org/1999/xhtml"})
        self.doctype_str='<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'

        self._head=SubElement(self._html,'head')
        Etitle=SubElement(self._head,'title')
        self._body=SubElement(self._html,'body')
        if title is not None:
            Etitle.text=str(title)
            self._title=SubElement(self._body,'h1')
            self._title.text=title

    def __str__(self):
        return self.doctype_str+'\n'+self.toprettyxml()

    def add_section(self,section_name):
        newSection=htmlSection(section_name)
        self._body.append(newSection._html)
        return newSection

    @property
    def body():
        return self._body

    @property
    def head():
        return self._head


class htmlSection(htmlChunk):

    def __init__(self,section_name,htmlElement=None):
        htmlChunk.__init__(self,'div',attrib={'id':section_name},parent=htmlElement)

        self.h3(section_name)
