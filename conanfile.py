import os, re
from conan import ConanFile, tools
from conan.tools.gnu import AutotoolsToolchain

class FFmpegConan(ConanFile):
    name = "openssl"
    version = "3.3.1"

    description = "openssl tls and crypto library"
    topics = ("audio", "video")
    url = "https://gitlab.worldiety.net/worldiety/customer/wdy/libriety/cpp/forks"
    homepage = "https://www.openssl.org/"
    license = "Apache 2"
        
    settings = "os", "arch", "compiler", "build_type"
    exports_sources = "*", "!autom4te.cache"
    python_requires = "wdyConanHelper/[]"
    python_requires_extend = "wdyConanHelper.ConanAutotools"

    options = {
        "shared": [True, False],
        "fPIC": [True, False],
    }
    default_options = {
        "shared": True,
        "fPIC": True,    
    }
 
    def _get_os(self):
        s = self.settings
        if hasattr(self, "settings_target") and self.settings_target: s = self.settings_target
        if s.os == "Android":
            if s.arch == "x86_64":
                return "no-asm android-x86_64" # asm on android-x64 seems broken (with clang)
            arch_map = {
                "armv7": "arm",
                "armv8": "arm64",
                "x86": "x86",
                "x86_64": "x86_64",
            }
            arch = arch_map[str(s.arch)]            
            return f"android-{arch}"
        elif s.os == "Windows" and s.arch == "x86_64":
            return "mingw64"
        elif s.os == "iOS":
            if s.os.sdk == "iphoneos":
                return "ios64-xcrun"
            elif s.os.sdk == "iphonesimulator":
                if s.arch == "armv8":
                    return "iossimulatorarm-xcrun"
                elif s.arch == "x86_64":
                    return "iossimulator-xcrun"
                else:
                    raise Exception(f"arch '{str(s.arch)}' not known for iphonesimulator")
            else:
                raise Exception(f"sdk '{str(s.sdk)}' not known for iOS")
        elif s.os == "Macos":
            if s.arch == "armv8":
                return "darwin64-arm64"
            elif s.arch == "x86_64":
                return "darwin64-x86_64"
        elif s.os == "Linux":
            if s.arch == "x86_64":
                return "linux-x86_64"
            elif s.arch == "x86":
                return "linux-x86"
            elif s.arch == "armv8":
                return "linux-aarch64"
            elif re.match("arm.*", str(s.arch)):
                return f"linux-armv4 -march={str(s.arch)}"
        raise Exception("architecture/os settings not mapped")
         
    # These could be configurable by conan options
    def _library_options(self):
        return [
            "enable-threads",
            "no-tests",
            
            f"--prefix={self.package_folder}",            
        ]
        
    def _build_options(self):
#        if not tools.cross_building(self):
#            return []            
        return self._get_os().split(" ")
        
       

    def _std_options(self):
        opts = []
        if self.options.fPIC:
            opts.append("enable-pic")
        else:
            opts.append("no-pic")
        if self.options.shared:
            opts = [ *opts, "enable-shared" ]
        else:
            opts = [ *opts, "no-shared" ]
        return opts
        
        
        
    def configure_autotools(self, tc: AutotoolsToolchain):        
        tc.extra_cflags.append(os.environ.get("CFLAGS", ""))
        tc.extra_cxxflags.append(os.environ.get("CXXFLAGS", ""))
        tc.extra_ldflags.append(os.environ.get("LDFLAGS", ""))

        cpp_flag = lambda x: (tc.extra_cflags.append(x), tc.extra_cxxflags.append(x))

        debug_prefix_mapping = f'-ffile-prefix-map="{os.path.abspath(self.source_folder)}"="{os.path.join("conan-pkg", self.name)}"'
        cpp_flag(debug_prefix_mapping)
        cpp_flag("-fexceptions")
        
        if self.settings.os == "Linux":
            tc.extra_ldflags.append("-Wl,--enable-new-dtags")
            
        buildStatic = hasattr(self.options, "shared") and not getattr(self.options, "shared")
            
        if hasattr(self.settings, "os") and getattr(self.settings, "os") != "Windows":
            wantsPIC = hasattr(self.options, "fPIC") and getattr(self.options, "fPIC")
            if wantsPIC or not buildStatic:
                cpp_flag("-fPIC")                
        
        if self.deps_env_info.SYSROOT:
                if self.settings.compiler in [ "clang", "apple-clang" ] and tools.apple.is_apple_os(self):
                    cpp_flag(f"-isysroot {self.deps_env_info.SYSROOT}")                    
                else:
                    cpp_flag(f"--sysroot={self.deps_env_info.SYSROOT}")                    

        tc.configure_args.clear()
        tc.configure_args += [
            *self._std_options(),
            *self._library_options(),
            *self._build_options(),            
        ]
        
        
    def build(self):
        tc = self._init_autotools()
        args = list( map(lambda x: f"'{x}'", tc.configure_args) )
        args = " ".join(args)
        
        with self.python_requires["wdyConanHelper"].module.utils.dependencies_environment(self, True).apply():                        
            with tc.environment().vars(self).apply():            
                self.output.info("configure-args: "+args)
                self.run("./Configure "+args)
                self.run(f"make -j{tools.build.build_jobs(self)}")
        
        
    def package(self):
        self.run(f"make install_sw install_ssldirs -j{tools.build.build_jobs(self)}")
        tools.files.rm(self, "*.la", os.path.join(self.package_folder, "lib"))
        

