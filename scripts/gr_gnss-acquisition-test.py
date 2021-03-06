#!/usr/bin/env python

from gnuradio import gr,usrp
from numpy import *
from gr_gnss import acquisition
from gps import ca_code
import pylab as p
import sys


class usrp_source(gr.hier_block2):
    def __init__(self, N, fs):
        gr.hier_block2.__init__(self,
                "usrp_source",
                gr.io_signature(0,0,0),
                gr.io_signature(1,1, gr.sizeof_gr_complex))

        # Parameters.
        frequency = 1575.6e6
        decim_rate = int(64e6/fs)
        fpga_filename = "std_4rx_0tx.rbf"

        # Sources.
        usrp = usrp.source_c( decim_rate=decim_rate, fpga_filename=fpga_filename )
        head = gr.head( gr.sizeof_gr_complex, N*fs*1e-3 )
        self.connect( usrp, head, self )

        # USRP settings.
        rx_subdev_spec = usrp.pick_rx_subdevice(usrp)
        usrp.set_mux(usrp.determine_rx_mux_value(usrp, rx_subdev_spec))
        subdev = usrp.selected_subdev( usrp, rx_subdev_spec )
        print "Subdev gain range: "
        print subdev.gain_range()

        subdev.set_gain(70)
        r = usrp.tune( 0,_subdev, frequency )
        if not r:
            sys.exit('Failed to set frequency')


class simulated_source(gr.hier_block2):
    def __init__(self, N, fs, fd, ca_shift, snr=0 ):
        gr.hier_block2.__init__(self,
                "simulated_source",
                gr.io_signature(0,0,0),
                gr.io_signature(1,1, gr.sizeof_gr_complex))

        code = ca_code(svn=1, fs=fs, ca_shift=ca_shift)
        code = ravel(array([ code for _ in range(N)]))

        n = arange(len(code))
        f = e**( 2j*pi*fd*n/fs )
        x = (code * f)

        # Add noise.
        signal_power = sum( sqrt(abs(x)))/len(x)
        noise_voltage = sqrt(signal_power/10**(snr/10.0))

        src = gr.vector_source_c(x)
        noise = gr.noise_source_c(gr.GR_UNIFORM, noise_voltage)
        add = gr.add_cc()
        self.connect(src, (add,0))
        self.connect(noise, (add,1))

        self.connect(add, self)


class file_source( gr.hier_block2 ):
    def __init__( self, filename, skip=0 ):
        gr.hier_block2.__init__( self,
                "file_source",
                gr.io_signature(0,0,0),
                gr.io_signature( 1,1,gr.sizeof_gr_complex ))

        src =  gr.file_source( gr.sizeof_gr_complex, filename )

        if skip>0:
            skip_head =  gr.skiphead( gr.sizeof_gr_complex, skip )
            self.connect( src, skip_head, self )
        else:
            self.connect(src, self)


class acquisition_test(gr.top_block):
    def __init__(self, filename="", fs=4e6):
        gr.top_block.__init__(self, "acquisition_test")

        # Parameters.
        svn = 1
        alpha = 0.05

        # Capture 10e6 samples.
#        src = usrp_source( N=2000, fs=fs )
        if filename:
            src = file_source( filename=filename )
        else:
            src = simulated_source( N=40, fs=fs, fd=3e3, ca_shift=200, snr=-11)

        acq = acquisition(fs=fs, svn=svn, alpha=alpha, fd_range=5)

        self.ca_sink = gr.vector_sink_f()
        self.fd_sink = gr.vector_sink_f()
        self.rmax_sink = gr.vector_sink_f()

        self.connect( src,  acq)
        self.connect( (acq, 0), self.ca_sink )
        self.connect( (acq, 1), self.fd_sink )
        self.connect( (acq, 2), self.rmax_sink )


def main():
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        fs = 4e6
    else:
        filename = ''

    top_block = acquisition_test(filename, fs)
    runtime = gr.runtime(top_block)

    try:
        runtime.start()
        runtime.wait()

        fig = p.figure()
        fig.subplots_adjust(hspace=1.4)

        p.subplot(3,1,1)
        p.plot( top_block.ca_sink.data())
        p.title("C/A code delay")
        p.xlabel("$t [ms]$")
        p.ylim(0,4000)

        p.subplot(3,1,2)
        p.plot( top_block.fd_sink.data())
        p.title("Doppler frequency estimate.")
        p.xlabel("$t [ms]$")
        p.ylim( -5e3, 5e3 )

        p.subplot(3,1,3)
        p.plot( top_block.rmax_sink.data())
        p.title("Correlation peak magnitude.")
        p.xlabel("$t [ms]$")

        p.show()
#        p.savefig("ca_fd_rmax.pdf")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

# vim: ai ts=4 sts=4 et sw=4
