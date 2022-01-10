set OS [lindex $tcl_platform(os) 0]
package ifneeded tkdnd 2.9.2 \
  "source \{$dir/tkdnd.tcl\} ; \
    if { $OS == "Windows" } {
        ::initialise \{$dir\} libtkdnd2.9.2[info sharedlibextension] tkdnd"
    } else {
        tkdnd::initialise \{$dir\} libtkdnd2.9.2.so tkdnd"
    }
  

package ifneeded tkdnd::utils 2.9.2 \
  "source \{$dir/tkdnd_utils.tcl\} ; \
   package provide tkdnd::utils 2.9.2"