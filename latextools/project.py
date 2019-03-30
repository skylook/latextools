import tempfile
import subprocess

import fs.memoryfs

from .pdf import Pdf


class LatexError(RuntimeError): pass


class LatexProject:
    def __init__(self, proj_fs=None):
        if proj_fs is None:
            proj_fs = fs.memoryfs.MemoryFS()
        self.proj_fs = proj_fs

    def add_file(self, path, text=None, data=None, file=None, fname=None):
        if ((text is not None)
                + (data is not None)
                + (file is not None)
                + (fname is not None)) != 1:
            raise TypeError(
                    'Specify exactly one of text, data, file, or fname.')
        if fname is not None:
            with open(fname, 'r') as f:
                self.add_file(path, file=f)
        elif file is not None:
            self.proj_fs.writefile(path, file)
        elif data is not None:
            self.proj_fs.writebytes(path, data)
        else:
            self.proj_fs.writetext(path, text)

    @staticmethod
    def _get_fs(base_dir=None, dst_fs=None):
        if (base_dir is not None) + (dst_fs is not None) < 1:
            raise TypeError('Specify at least one argument.')
        if base_dir is None:
            return dst_fs
        elif dst_fs is None:
            return fs.open_fs(base_dir, writeable=True)
        else:
            return dst_fs.opendir(base_dir)

    def write_src(self, base_dir=None, dst_fs=None):
        dst_fs = self._get_fs(base_dir, dst_fs)
        fs.copy.copy_dir(self.proj_fs, '/', dst_fs, '/')

    @staticmethod
    def _get_output_fname(fname, out_extension='pdf'):
        comps = fname.split('.')
        if len(comps) <= 1:
            comps.append(out_extension)
        else:
            comps[-1] = out_extension
        return '.'.join(comps)

    def compile_pdf(self, fname='main.tex', tmp_dir=None,
                    return_path=False, **pdf_args):
        return self.compile_pdf_batch([fname], tmp_dir=tmp_dir,
                                      return_path=return_path,
                                      **pdf_args)[0]

    def compile_pdf_batch(self, fname_list, tmp_dir=None,
                          return_path=False, **pdf_args):
        if tmp_dir is None:
            with tempfile.TemporaryDirectory() as tmp_dir:
                return self.compile_pdf_batch(
                                fname_list, tmp_dir=tmp_dir,
                                return_path=return_path,
                                **pdf_args)
        tmp_fs = fs.open_fs(tmp_dir, writeable=False)
        self.write_src(tmp_dir)
        out_list = []
        for fname in fname_list:
            fpath = fs.path.join(tmp_dir, fname)
            self.run_pdflatex(fpath, cwd=tmp_dir)
            out_fname = self._get_output_fname(fname, 'pdf')
            pdf = None
            if tmp_fs.exists(out_fname):
                if not return_path:
                    data = tmp_fs.readbytes(out_fname)
                    pdf = Pdf(data=data, **pdf_args)
            else:
                out_fname = None
            out_list.append(out_fname if return_path else pdf)
        return out_list

    def save_pdf(self, fname='main.tex', base_dir=None, dst_fs=None,
                 tmp_dir=None):
        self.save_pdf_batch([fname], base_dir=base_dir, dst_fs=dst_fs,
                            tmp_dir=tmp_dir)

    def save_pdf_batch(self, fname_list, base_dir=None, dst_fs=None,
                       tmp_dir=None):
        if tmp_dir is None:
            with tempfile.TemporaryDirectory() as tmp_dir:
                return self.save_pdf_batch(
                            fname_list, base_dir=base_dir,
                            dst_fs=dst_fs, tmp_dir=tmp_dir)

        dst_fs = self._get_fs(base_dir, dst_fs)
        base_dir = '/'
        tmp_fs = fs.open_fs(tmp_dir, writeable=False)

        out_fname_list = self.compile_pdf_batch(
                                fname_list, tmp_dir=tmp_dir,
                                return_path=True)
        for fname in out_fname_list:
            dst_fs.makedir(fs.path.dirname(fname), recreate=True)
            fs.copy.copy_file(tmp_fs, fname, dst_fs, fname)

    def run_pdflatex(self, fpath, cwd):
        try:
            p = subprocess.Popen(['pdflatex', 'main.tex'],
                                 cwd=cwd,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        except FileNotFoundError:
            raise LatexError('Latex compiler pdflatex not found.')
        stdout, stderr = p.communicate()
        if p.returncode != 0:
            # pdflatex had an error
            msg = ''
            if stdout:
                msg += stdout.decode()
            if stderr:
                msg += stderr.decode()
            raise LatexError(msg)
