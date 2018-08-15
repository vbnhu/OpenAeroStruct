from __future__ import print_function, division
import numpy as np

from openmdao.api import ExplicitComponent

class WaveDrag(ExplicitComponent):
    """
    Compute the wave drag if the with_wave option is True.
    If not, the CDw is 0.
    This component exists for each lifting surface.

    Parameters
    ----------
    M : float
        Mach number.
    sweep : float
        The angle (in degrees) of the wing sweep. This is used in the form
        factor calculation.
    lengths[ny] : numpy array
        The sum of the lengths of each line segment along a chord section.

    Returns
    -------
    CDw : float
        Wave drag coefficient for the lifting surface computed using the 
        Korn equation
    """

    def initialize(self):
        self.options.declare('surface', types=dict)
        self.options.declare('with_wave', types=bool)

    def setup(self):
        self.surface = surface = self.options['surface']
        self.with_wave = surface['with_wave']

        # Thickness over chord for the airfoil
        self.t_over_c = surface['t_over_c']
        self.ka = 0.95  # airfoil technology level

        ny = surface['num_y']

        self.add_input('M', val=1.6)
        self.add_input('cos_sweep', val=np.ones((ny-1))*.2, units='m')
        self.add_input('widths', val=np.arange((ny-1))+1., units='m')
        self.add_input('CL', val=0.33)
        self.add_input('chords', val=np.ones((ny)), units='m')
        self.add_output('CDw', val=0.)

        self.declare_partials('CDw', '*')
        self.set_check_partial_options(wrt='*', method='cs', step=1e-50)

    def compute(self, inputs, outputs):
        if self.with_wave:
            t_over_c = self.t_over_c
            widths = inputs['widths']
            actual_cos_sweep = np.divide(inputs['cos_sweep'],widths)
            M = inputs['M']
            chords = inputs['chords']
            CL = inputs['CL']
            mean_chords = (chords[:-1] + chords[1:]) / 2.
            panel_areas = mean_chords * inputs['cos_sweep']
            avg_cos_sweep = np.sum(actual_cos_sweep * panel_areas) / np.sum(panel_areas) # weighted average of 1/4 chord sweep
            MDD = self.ka / avg_cos_sweep - t_over_c / avg_cos_sweep**2 - CL / (10*avg_cos_sweep**3)
            Mcrit = MDD - (0.1 / 80.)**(1./3.)

            if M > Mcrit:
                outputs['CDw'] = 20*(M - Mcrit)**4
            else:
                outputs['CDw'] = 0.0

            if self.surface['symmetry']:
                outputs['CDw'] *= 2
        else:
            outputs['CDw'] = 0.0

    def compute_partials(self, inputs, partials):
        """ Jacobian for wave drag."""
        if self.with_wave:
            ny = self.surface['num_y']
            t_over_c = self.t_over_c
            widths = inputs['widths']
            cos_sweep = inputs['cos_sweep']
            actual_cos_sweep = cos_sweep/widths
            M = inputs['M']
            chords = inputs['chords']
            CL = inputs['CL']

            chords = np.mean((chords[:-1],chords[1:]))
            panel_areas = chords * inputs['cos_sweep']
            avg_cos_sweep = np.sum(actual_cos_sweep * panel_areas) / np.sum(panel_areas)
            MDD = 0.95 / avg_cos_sweep - t_over_c / avg_cos_sweep**2 - CL / (10*avg_cos_sweep**3)
            Mcrit = MDD - (0.1 / 80.)**(1./3.)

            if M > Mcrit:
                dCDwdMDD = -80*(M-Mcrit)**3
                dMDDdCL = -1./(10*avg_cos_sweep**3)
                dMDDdavg = (-10*self.ka*avg_cos_sweep**2 + 20*t_over_c*avg_cos_sweep+3*CL)/(10*avg_cos_sweep**4)
                ccos = np.sum(cos_sweep*chords)
                ccos2w = np.sum(chords*cos_sweep**2/widths)
                davgdcos = 2*chords*cos_sweep/widths/ccos - chords*ccos2w/ccos**2
                davgdw = -1*chords*cos_sweep**2/widths**2/ccos
                davgdc = cos_sweep**2/widths/ccos - cos_sweep*ccos2w/ccos**2
                #davgdc = np.atleast_2d(davgdc)
                dcdchords = np.zeros((ny-1,ny))
                i,j = np.indices(dcdchords.shape)
                dcdchords[i==j] = 0.5
                dcdchords[i==j-1] = 0.5


                partials['CDw','M'] = -1*dCDwdMDD
                partials['CDw','CL'] = dCDwdMDD * dMDDdCL
                partials['CDw','widths'] = dCDwdMDD * dMDDdavg * davgdw
                partials['CDw','cos_sweep'] = dCDwdMDD * dMDDdavg * davgdcos
                partials['CDw','chords'] = dCDwdMDD * dMDDdavg * np.matmul(davgdc, dcdchords)

                
        if self.surface['symmetry']:
            partials['CDw', 'CL'][0, :] *=  2
            partials['CDw', 'widths'][0, :] *= 2
            partials['CDw', 'cos_sweep'][0, :] *=  2
            partials['CDw', 'M'][0, :] *=  2
            partials['CDw', 'chords'][0, :] *=  2