#include <Python.h>
#include "mspack.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <errno.h>
#include <sys/types.h>
#ifdef __APPLE__
#include <dlfcn.h>
#endif

#ifndef MSCABD_COMP_MASK
#define MSCABD_COMP_MASK 0x000f
#endif
#ifndef MSCABD_COMP_NONE
#define MSCABD_COMP_NONE 0x0000
#endif
#ifndef MSCABD_COMP_MSZIP
#define MSCABD_COMP_MSZIP 0x0001
#endif
#ifndef MSCABD_COMP_QUANTUM
#define MSCABD_COMP_QUANTUM 0x0002
#endif
#ifndef MSCABD_COMP_LZX
#define MSCABD_COMP_LZX 0x0003
#endif

#ifndef MSCAB_ATTRIB_RDONLY
#define MSCAB_ATTRIB_RDONLY 0x01
#endif
#ifndef MSCAB_ATTRIB_HIDDEN
#define MSCAB_ATTRIB_HIDDEN 0x02
#endif
#ifndef MSCAB_ATTRIB_SYSTEM
#define MSCAB_ATTRIB_SYSTEM 0x04
#endif
#ifndef MSCAB_ATTRIB_ARCH
#define MSCAB_ATTRIB_ARCH 0x20
#endif

#ifndef MSPACK_ERR_OK
#define MSPACK_ERR_OK 0
#endif
#ifndef MSPACK_ERR_ARGS
#define MSPACK_ERR_ARGS 1
#endif
#ifndef MSPACK_ERR_OPEN
#define MSPACK_ERR_OPEN 2
#endif
#ifndef MSPACK_ERR_READ
#define MSPACK_ERR_READ 3
#endif
#ifndef MSPACK_ERR_WRITE
#define MSPACK_ERR_WRITE 4
#endif
#ifndef MSPACK_ERR_SEEK
#define MSPACK_ERR_SEEK 5
#endif
#ifndef MSPACK_ERR_NOMEMORY
#define MSPACK_ERR_NOMEMORY 6
#endif
#ifndef MSPACK_ERR_SIGNATURE
#define MSPACK_ERR_SIGNATURE 7
#endif
#ifndef MSPACK_ERR_DATAFORMAT
#define MSPACK_ERR_DATAFORMAT 8
#endif
#ifndef MSPACK_ERR_CHECKSUM
#define MSPACK_ERR_CHECKSUM 9
#endif
#ifndef MSPACK_ERR_CRUNCH
#define MSPACK_ERR_CRUNCH 10
#endif
#ifndef MSPACK_ERR_DECRUNCH
#define MSPACK_ERR_DECRUNCH 11
#endif
#ifndef MSPACK_ERR_BADCOMP
#define MSPACK_ERR_BADCOMP 12
#endif
#ifndef MSSZDD_FMT_NORMAL
#define MSSZDD_FMT_NORMAL 0
#endif
#ifndef MSSZDD_FMT_QBASIC
#define MSSZDD_FMT_QBASIC 1
#endif
#ifndef MSKWAJ_COMP_NONE
#define MSKWAJ_COMP_NONE 0
#endif
#ifndef MSKWAJ_COMP_XOR
#define MSKWAJ_COMP_XOR 1
#endif
#ifndef MSKWAJ_COMP_SZDD
#define MSKWAJ_COMP_SZDD 2
#endif
#ifndef MSKWAJ_COMP_LZH
#define MSKWAJ_COMP_LZH 3
#endif
#ifndef MSKWAJ_COMP_MSZIP
#define MSKWAJ_COMP_MSZIP 4
#endif
#ifndef MSKWAJ_HDR_HASLENGTH
#define MSKWAJ_HDR_HASLENGTH 0x01
#endif
#ifndef MSKWAJ_HDR_HASUNKNOWN1
#define MSKWAJ_HDR_HASUNKNOWN1 0x02
#endif
#ifndef MSKWAJ_HDR_HASUNKNOWN2
#define MSKWAJ_HDR_HASUNKNOWN2 0x04
#endif
#ifndef MSKWAJ_HDR_HASFILENAME
#define MSKWAJ_HDR_HASFILENAME 0x08
#endif
#ifndef MSKWAJ_HDR_HASFILEEXT
#define MSKWAJ_HDR_HASFILEEXT 0x10
#endif
#ifndef MSKWAJ_HDR_HASEXTRATEXT
#define MSKWAJ_HDR_HASEXTRATEXT 0x20
#endif

static PyObject *decode_filename(const char *name) {
    if (!name) {
        Py_RETURN_NONE;
    }
    return PyUnicode_DecodeUTF8(name, (Py_ssize_t)strlen(name), "surrogateescape");
}

static unsigned int dos_date_from_parts(int year, int month, int day) {
    if (year < 1980 || year > 2107) return 0;
    if (month < 1 || month > 12) return 0;
    if (day < 1 || day > 31) return 0;
    return (unsigned int)(((year - 1980) << 9) | (month << 5) | day);
}

static unsigned int dos_time_from_parts(int hour, int minute, int second) {
    if (hour < 0 || hour > 23) return 0;
    if (minute < 0 || minute > 59) return 0;
    if (second < 0 || second > 59) return 0;
    return (unsigned int)((hour << 11) | (minute << 5) | (second / 2));
}

struct mscab_decompressor;

#ifdef __APPLE__
typedef struct mscab_decompressor *(*cabd_create_fn)(struct mspack_system *sys);
typedef void (*cabd_destroy_fn)(struct mscab_decompressor *self);
typedef struct mschm_decompressor *(*chmd_create_fn)(struct mspack_system *sys);
typedef void (*chmd_destroy_fn)(struct mschm_decompressor *self);
typedef struct msszdd_decompressor *(*szddd_create_fn)(struct mspack_system *sys);
typedef void (*szddd_destroy_fn)(struct msszdd_decompressor *self);
typedef struct mskwaj_decompressor *(*kwajd_create_fn)(struct mspack_system *sys);
typedef void (*kwajd_destroy_fn)(struct mskwaj_decompressor *self);
static cabd_create_fn g_cabd_create = NULL;
static cabd_destroy_fn g_cabd_destroy = NULL;
static chmd_create_fn g_chmd_create = NULL;
static chmd_destroy_fn g_chmd_destroy = NULL;
static szddd_create_fn g_szdd_create = NULL;
static szddd_destroy_fn g_szdd_destroy = NULL;
static kwajd_create_fn g_kwaj_create = NULL;
static kwajd_destroy_fn g_kwaj_destroy = NULL;
static void *g_mspack_handle = NULL;

static int ensure_mspack_loaded(const char *path) {
    if (g_cabd_create && g_cabd_destroy) {
        return 0;
    }
    g_mspack_handle = dlopen(path, RTLD_NOW | RTLD_LOCAL);
    if (!g_mspack_handle) {
        return -1;
    }
    g_cabd_create = (cabd_create_fn)dlsym(g_mspack_handle, "mspack_create_cab_decompressor");
    g_cabd_destroy = (cabd_destroy_fn)dlsym(g_mspack_handle, "mspack_destroy_cab_decompressor");
    g_chmd_create = (chmd_create_fn)dlsym(g_mspack_handle, "mspack_create_chm_decompressor");
    g_chmd_destroy = (chmd_destroy_fn)dlsym(g_mspack_handle, "mspack_destroy_chm_decompressor");
    g_szdd_create = (szddd_create_fn)dlsym(g_mspack_handle, "mspack_create_szdd_decompressor");
    g_szdd_destroy = (szddd_destroy_fn)dlsym(g_mspack_handle, "mspack_destroy_szdd_decompressor");
    g_kwaj_create = (kwajd_create_fn)dlsym(g_mspack_handle, "mspack_create_kwaj_decompressor");
    g_kwaj_destroy = (kwajd_destroy_fn)dlsym(g_mspack_handle, "mspack_destroy_kwaj_decompressor");
    if (!g_cabd_create || !g_cabd_destroy || !g_chmd_create || !g_chmd_destroy ||
        !g_szdd_create || !g_szdd_destroy || !g_kwaj_create || !g_kwaj_destroy) {
        return -1;
    }
    return 0;
}
#endif

static struct mscab_decompressor *cabd_create(struct mspack_system *sys) {
#ifdef __APPLE__
    if (g_cabd_create == NULL || g_cabd_destroy == NULL) return NULL;
    return g_cabd_create(sys);
#else
    return mspack_create_cab_decompressor(sys);
#endif
}

static void cabd_destroy(struct mscab_decompressor *cabd) {
#ifdef __APPLE__
    if (g_cabd_destroy) {
        g_cabd_destroy(cabd);
    }
#else
    mspack_destroy_cab_decompressor(cabd);
#endif
}

static struct mschm_decompressor *chmd_create(struct mspack_system *sys) {
#ifdef __APPLE__
    if (g_chmd_create == NULL || g_chmd_destroy == NULL) return NULL;
    return g_chmd_create(sys);
#else
    return mspack_create_chm_decompressor(sys);
#endif
}

static void chmd_destroy(struct mschm_decompressor *chmd) {
#ifdef __APPLE__
    if (g_chmd_destroy) {
        g_chmd_destroy(chmd);
    }
#else
    mspack_destroy_chm_decompressor(chmd);
#endif
}

static struct msszdd_decompressor *szddd_create(struct mspack_system *sys) {
#ifdef __APPLE__
    if (g_szdd_create == NULL || g_szdd_destroy == NULL) return NULL;
    return g_szdd_create(sys);
#else
    return mspack_create_szdd_decompressor(sys);
#endif
}

static void szddd_destroy(struct msszdd_decompressor *szdd) {
#ifdef __APPLE__
    if (g_szdd_destroy) {
        g_szdd_destroy(szdd);
    }
#else
    mspack_destroy_szdd_decompressor(szdd);
#endif
}

static struct mskwaj_decompressor *kwajd_create(struct mspack_system *sys) {
#ifdef __APPLE__
    if (g_kwaj_create == NULL || g_kwaj_destroy == NULL) return NULL;
    return g_kwaj_create(sys);
#else
    return mspack_create_kwaj_decompressor(sys);
#endif
}

static void kwajd_destroy(struct mskwaj_decompressor *kwaj) {
#ifdef __APPLE__
    if (g_kwaj_destroy) {
        g_kwaj_destroy(kwaj);
    }
#else
    mspack_destroy_kwaj_decompressor(kwaj);
#endif
}

struct memcab_system;

struct memcab_file {
    int is_mem;
    const unsigned char *data;
    size_t size;
    size_t pos;
    FILE *fp;
};

struct memcab_system {
    struct mspack_system sys;
    const unsigned char *data;
    size_t size;
    const char *mem_name;
};

static struct mspack_file *mem_open(struct mspack_system *self, const char *filename, int mode) {
    struct memcab_system *msys = (struct memcab_system *)self;
    struct memcab_file *mf = (struct memcab_file *)malloc(sizeof(struct memcab_file));
    if (!mf) return NULL;
    memset(mf, 0, sizeof(*mf));

    if (filename && msys->mem_name && strcmp(filename, msys->mem_name) == 0) {
        if (mode != MSPACK_SYS_OPEN_READ) {
            free(mf);
            return NULL;
        }
        mf->is_mem = 1;
        mf->data = msys->data;
        mf->size = msys->size;
        mf->pos = 0;
        mf->fp = NULL;
        return (struct mspack_file *)mf;
    }

    const char *fmode = NULL;
    switch (mode) {
        case MSPACK_SYS_OPEN_READ:
            fmode = "rb";
            break;
        case MSPACK_SYS_OPEN_WRITE:
            fmode = "wb";
            break;
        case MSPACK_SYS_OPEN_UPDATE:
            fmode = "rb+";
            break;
        case MSPACK_SYS_OPEN_APPEND:
            fmode = "ab+";
            break;
        default:
            free(mf);
            return NULL;
    }
    mf->fp = fopen(filename, fmode);
    if (!mf->fp) {
        free(mf);
        return NULL;
    }
    mf->is_mem = 0;
    return (struct mspack_file *)mf;
}

static void mem_close(struct mspack_file *file) {
    struct memcab_file *mf = (struct memcab_file *)file;
    if (!mf) return;
    if (!mf->is_mem && mf->fp) {
        fclose(mf->fp);
    }
    free(mf);
}

static int mem_read(struct mspack_file *file, void *buffer, int bytes) {
    struct memcab_file *mf = (struct memcab_file *)file;
    if (!mf || bytes <= 0) return 0;
    if (mf->is_mem) {
        size_t remain = (mf->pos < mf->size) ? (mf->size - mf->pos) : 0;
        size_t to_read = (size_t)bytes;
        if (to_read > remain) to_read = remain;
        if (to_read > 0) {
            memcpy(buffer, mf->data + mf->pos, to_read);
            mf->pos += to_read;
        }
        return (int)to_read;
    }
    return (int)fread(buffer, 1, (size_t)bytes, mf->fp);
}

static int mem_write(struct mspack_file *file, void *buffer, int bytes) {
    struct memcab_file *mf = (struct memcab_file *)file;
    if (!mf || bytes <= 0) return 0;
    if (mf->is_mem) {
        return -1;
    }
    return (int)fwrite(buffer, 1, (size_t)bytes, mf->fp);
}

static int mem_seek(struct mspack_file *file, off_t offset, int mode) {
    struct memcab_file *mf = (struct memcab_file *)file;
    if (!mf) return -1;
    if (mf->is_mem) {
        off_t base = 0;
        if (mode == MSPACK_SYS_SEEK_CUR) base = (off_t)mf->pos;
        else if (mode == MSPACK_SYS_SEEK_END) base = (off_t)mf->size;
        else if (mode != MSPACK_SYS_SEEK_START) return -1;
        off_t npos = base + offset;
        if (npos < 0 || (size_t)npos > mf->size) return -1;
        mf->pos = (size_t)npos;
        return 0;
    }
#if defined(_WIN32)
    return _fseeki64(mf->fp, offset, mode) == 0 ? 0 : -1;
#else
    return fseeko(mf->fp, offset, mode) == 0 ? 0 : -1;
#endif
}

static off_t mem_tell(struct mspack_file *file) {
    struct memcab_file *mf = (struct memcab_file *)file;
    if (!mf) return (off_t)-1;
    if (mf->is_mem) return (off_t)mf->pos;
#if defined(_WIN32)
    return (off_t)_ftelli64(mf->fp);
#else
    return (off_t)ftello(mf->fp);
#endif
}

static void mem_message(struct mspack_file *file, const char *format, ...) {
    (void)file;
    (void)format;
}

static void *mem_alloc(struct mspack_system *self, size_t bytes) {
    (void)self;
    return malloc(bytes);
}

static void mem_free(void *ptr) {
    free(ptr);
}

static void mem_copy(void *src, void *dest, size_t bytes) {
    memcpy(dest, src, bytes);
}

static int dict_set_owned(PyObject *dict, const char *key, PyObject *value) {
    if (!value) {
        return -1;
    }
    if (PyDict_SetItemString(dict, key, value) < 0) {
        Py_DECREF(value);
        return -1;
    }
    Py_DECREF(value);
    return 0;
}

static const char *compression_name(unsigned int comp_type) {
    unsigned int comp = comp_type & MSCABD_COMP_MASK;
    switch (comp) {
        case MSCABD_COMP_NONE:
            return "none";
        case MSCABD_COMP_MSZIP:
            return "mszip";
        case MSCABD_COMP_QUANTUM:
            return "quantum";
        case MSCABD_COMP_LZX:
            return "lzx";
        default:
            return "unknown";
    }
}

static int folder_index(struct mscabd_folder *folders, struct mscabd_folder *target) {
    int idx = 0;
    while (folders) {
        if (folders == target) {
            return idx;
        }
        folders = folders->next;
        idx++;
    }
    return -1;
}

static int count_files(struct mscabd_file *file) {
    int count = 0;
    while (file) {
        count++;
        file = file->next;
    }
    return count;
}

static int count_folders(struct mscabd_folder *folder) {
    int count = 0;
    while (folder) {
        count++;
        folder = folder->next;
    }
    return count;
}

static PyObject *build_cab_info(struct mscabd_cabinet *cab, const char *mem_name) {
    PyObject *dict = PyDict_New();
    if (!dict) return NULL;

    PyObject *py_filename = decode_filename(cab->filename);
    if (mem_name && cab->filename && strcmp(cab->filename, mem_name) == 0) {
        Py_XDECREF(py_filename);
        Py_INCREF(Py_None);
        py_filename = Py_None;
    } else if (!py_filename) {
        Py_INCREF(Py_None);
        py_filename = Py_None;
    }
    if (dict_set_owned(dict, "filename", py_filename) < 0) goto error;

    if (dict_set_owned(dict, "base_offset", PyLong_FromLongLong((long long)cab->base_offset)) < 0) goto error;
    if (dict_set_owned(dict, "length", PyLong_FromUnsignedLong((unsigned long)cab->length)) < 0) goto error;
    if (dict_set_owned(dict, "set_id", PyLong_FromUnsignedLong((unsigned long)cab->set_id)) < 0) goto error;
    if (dict_set_owned(dict, "set_index", PyLong_FromUnsignedLong((unsigned long)cab->set_index)) < 0) goto error;
    if (dict_set_owned(dict, "header_resv", PyLong_FromUnsignedLong((unsigned long)cab->header_resv)) < 0) goto error;
    if (dict_set_owned(dict, "flags", PyLong_FromLong((long)cab->flags)) < 0) goto error;

    int has_prev = cab->prevname && cab->prevname[0];
    int has_next = cab->nextname && cab->nextname[0];
    if (dict_set_owned(dict, "has_prev", PyBool_FromLong(has_prev)) < 0) goto error;
    if (dict_set_owned(dict, "has_next", PyBool_FromLong(has_next)) < 0) goto error;

    PyObject *py_prev = decode_filename(cab->prevname);
    PyObject *py_next = decode_filename(cab->nextname);
    PyObject *py_previnfo = decode_filename(cab->previnfo);
    PyObject *py_nextinfo = decode_filename(cab->nextinfo);
    if (!has_prev) {
        Py_XDECREF(py_prev);
        Py_XDECREF(py_previnfo);
        Py_INCREF(Py_None);
        Py_INCREF(Py_None);
        py_prev = Py_None;
        py_previnfo = Py_None;
    }
    if (!has_next) {
        Py_XDECREF(py_next);
        Py_XDECREF(py_nextinfo);
        Py_INCREF(Py_None);
        Py_INCREF(Py_None);
        py_next = Py_None;
        py_nextinfo = Py_None;
    }
    if (dict_set_owned(dict, "prev_cabinet", py_prev) < 0) goto error;
    if (dict_set_owned(dict, "next_cabinet", py_next) < 0) goto error;
    if (dict_set_owned(dict, "prev_disk", py_previnfo) < 0) goto error;
    if (dict_set_owned(dict, "next_disk", py_nextinfo) < 0) goto error;

    if (dict_set_owned(dict, "files_count", PyLong_FromLong(count_files(cab->files))) < 0) goto error;
    if (dict_set_owned(dict, "folders_count", PyLong_FromLong(count_folders(cab->folders))) < 0) goto error;

    return dict;

error:
    Py_DECREF(dict);
    return NULL;
}

static PyObject *py_cab_list(PyObject *self, PyObject *args) {
    PyObject *path_obj = NULL;
    PyObject *path_bytes = NULL;
    const char *path = NULL;

    if (!PyArg_ParseTuple(args, "O", &path_obj)) {
        return NULL;
    }
    if (!PyUnicode_FSConverter(path_obj, &path_bytes)) {
        return NULL;
    }
    path = PyBytes_AS_STRING(path_bytes);

    struct mscab_decompressor *cabd = cabd_create(NULL);
    if (!cabd) {
        Py_DECREF(path_bytes);
        return Py_BuildValue("Oi", Py_None, MSPACK_ERR_NOMEMORY);
    }

    struct mscabd_cabinet *cab = cabd->open(cabd, path);
    if (!cab) {
        int err = cabd->last_error(cabd);
        cabd_destroy(cabd);
        Py_DECREF(path_bytes);
        return Py_BuildValue("Oi", Py_None, err);
    }

    PyObject *list = PyList_New(0);
    if (!list) {
        cabd->close(cabd, cab);
        cabd_destroy(cabd);
        Py_DECREF(path_bytes);
        return NULL;
    }

    int has_prev = cab->prevname && cab->prevname[0];
    int has_next = cab->nextname && cab->nextname[0];

    struct mscabd_file *file = cab->files;
    while (file) {
        PyObject *dict = PyDict_New();
        if (!dict) {
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            Py_DECREF(path_bytes);
            return NULL;
        }

        PyObject *py_name = decode_filename(file->filename);
        if (!py_name) {
            Py_INCREF(Py_None);
            py_name = Py_None;
        }
        if (dict_set_owned(dict, "name", py_name) < 0) {
            Py_DECREF(dict);
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            Py_DECREF(path_bytes);
            return NULL;
        }

        unsigned int dos_date = dos_date_from_parts(file->date_y, file->date_m, file->date_d);
        unsigned int dos_time = dos_time_from_parts(file->time_h, file->time_m, file->time_s);
        if (dict_set_owned(dict, "size", PyLong_FromUnsignedLong((unsigned long)file->length)) < 0 ||
            dict_set_owned(dict, "dos_date", PyLong_FromUnsignedLong((unsigned long)dos_date)) < 0 ||
            dict_set_owned(dict, "dos_time", PyLong_FromUnsignedLong((unsigned long)dos_time)) < 0 ||
            dict_set_owned(dict, "attrs", PyLong_FromUnsignedLong((unsigned long)file->attribs)) < 0) {
            Py_DECREF(dict);
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            Py_DECREF(path_bytes);
            return NULL;
        }

        if (dict_set_owned(dict, "date_y", PyLong_FromLong((long)file->date_y)) < 0 ||
            dict_set_owned(dict, "date_m", PyLong_FromLong((long)file->date_m)) < 0 ||
            dict_set_owned(dict, "date_d", PyLong_FromLong((long)file->date_d)) < 0 ||
            dict_set_owned(dict, "time_h", PyLong_FromLong((long)file->time_h)) < 0 ||
            dict_set_owned(dict, "time_m", PyLong_FromLong((long)file->time_m)) < 0 ||
            dict_set_owned(dict, "time_s", PyLong_FromLong((long)file->time_s)) < 0) {
            Py_DECREF(dict);
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            Py_DECREF(path_bytes);
            return NULL;
        }

        if (dict_set_owned(dict, "is_readonly", PyBool_FromLong((file->attribs & MSCAB_ATTRIB_RDONLY) != 0)) < 0 ||
            dict_set_owned(dict, "is_hidden", PyBool_FromLong((file->attribs & MSCAB_ATTRIB_HIDDEN) != 0)) < 0 ||
            dict_set_owned(dict, "is_system", PyBool_FromLong((file->attribs & MSCAB_ATTRIB_SYSTEM) != 0)) < 0 ||
            dict_set_owned(dict, "is_archive", PyBool_FromLong((file->attribs & MSCAB_ATTRIB_ARCH) != 0)) < 0) {
            Py_DECREF(dict);
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            Py_DECREF(path_bytes);
            return NULL;
        }

        int fidx = folder_index(cab->folders, file->folder);
        if (dict_set_owned(dict, "folder_index", PyLong_FromLong(fidx)) < 0 ||
            dict_set_owned(dict, "offset", PyLong_FromLongLong((long long)file->offset)) < 0) {
            Py_DECREF(dict);
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            Py_DECREF(path_bytes);
            return NULL;
        }

        const char *comp = "unknown";
        if (file->folder) {
            comp = compression_name(file->folder->comp_type);
        }
        if (dict_set_owned(dict, "compression", PyUnicode_FromString(comp)) < 0) {
            Py_DECREF(dict);
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            Py_DECREF(path_bytes);
            return NULL;
        }

        if (dict_set_owned(dict, "has_prev", PyBool_FromLong(has_prev)) < 0 ||
            dict_set_owned(dict, "has_next", PyBool_FromLong(has_next)) < 0) {
            Py_DECREF(dict);
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            Py_DECREF(path_bytes);
            return NULL;
        }
        PyObject *py_prev = decode_filename(cab->prevname);
        PyObject *py_next = decode_filename(cab->nextname);
        if (!has_prev) {
            Py_XDECREF(py_prev);
            py_prev = Py_None;
            Py_INCREF(Py_None);
        }
        if (!has_next) {
            Py_XDECREF(py_next);
            py_next = Py_None;
            Py_INCREF(Py_None);
        }
        if (dict_set_owned(dict, "prev_cabinet", py_prev) < 0 ||
            dict_set_owned(dict, "next_cabinet", py_next) < 0) {
            Py_DECREF(dict);
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            Py_DECREF(path_bytes);
            return NULL;
        }

        if (!has_prev && !has_next && cab->set_id == 0 && cab->set_index == 0) {
            Py_INCREF(Py_None);
            if (dict_set_owned(dict, "cabinet_set_id", Py_None) < 0) {
                Py_DECREF(dict);
                Py_DECREF(list);
                cabd->close(cabd, cab);
                cabd_destroy(cabd);
                Py_DECREF(path_bytes);
                return NULL;
            }
            Py_INCREF(Py_None);
            if (dict_set_owned(dict, "cabinet_set_index", Py_None) < 0) {
                Py_DECREF(dict);
                Py_DECREF(list);
                cabd->close(cabd, cab);
                cabd_destroy(cabd);
                Py_DECREF(path_bytes);
                return NULL;
            }
        } else {
            if (dict_set_owned(dict, "cabinet_set_id", PyLong_FromUnsignedLong((unsigned long)cab->set_id)) < 0 ||
                dict_set_owned(dict, "cabinet_set_index", PyLong_FromUnsignedLong((unsigned long)cab->set_index)) < 0) {
                Py_DECREF(dict);
                Py_DECREF(list);
                cabd->close(cabd, cab);
                cabd_destroy(cabd);
                Py_DECREF(path_bytes);
                return NULL;
            }
        }

        if (PyList_Append(list, dict) < 0) {
            Py_DECREF(dict);
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            Py_DECREF(path_bytes);
            return NULL;
        }
        Py_DECREF(dict);
        file = file->next;
    }

    cabd->close(cabd, cab);
    cabd_destroy(cabd);
    Py_DECREF(path_bytes);

    return Py_BuildValue("Oi", list, MSPACK_ERR_OK);
}

static PyObject *py_cab_list_bytes(PyObject *self, PyObject *args) {
    Py_buffer buf;
    if (!PyArg_ParseTuple(args, "y*", &buf)) {
        return NULL;
    }

    const char *mem_name = "pylibmspack:memcab";
    struct memcab_system sys;
    memset(&sys, 0, sizeof(sys));
    sys.data = (const unsigned char *)buf.buf;
    sys.size = (size_t)buf.len;
    sys.mem_name = mem_name;
    sys.sys.open = mem_open;
    sys.sys.close = mem_close;
    sys.sys.read = mem_read;
    sys.sys.write = mem_write;
    sys.sys.seek = mem_seek;
    sys.sys.tell = mem_tell;
    sys.sys.message = mem_message;
    sys.sys.alloc = mem_alloc;
    sys.sys.free = mem_free;
    sys.sys.copy = mem_copy;
    sys.sys.null_ptr = NULL;

    struct mscab_decompressor *cabd = cabd_create(&sys.sys);
    if (!cabd) {
        PyBuffer_Release(&buf);
        return Py_BuildValue("Oi", Py_None, MSPACK_ERR_NOMEMORY);
    }

    struct mscabd_cabinet *cab = cabd->open(cabd, mem_name);
    if (!cab) {
        int err = cabd->last_error(cabd);
        cabd_destroy(cabd);
        PyBuffer_Release(&buf);
        return Py_BuildValue("Oi", Py_None, err);
    }

    PyObject *list = PyList_New(0);
    if (!list) {
        cabd->close(cabd, cab);
        cabd_destroy(cabd);
        PyBuffer_Release(&buf);
        return NULL;
    }

    int has_prev = cab->prevname && cab->prevname[0];
    int has_next = cab->nextname && cab->nextname[0];

    struct mscabd_file *file = cab->files;
    while (file) {
        PyObject *dict = PyDict_New();
        if (!dict) {
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            PyBuffer_Release(&buf);
            return NULL;
        }

        PyObject *py_name = decode_filename(file->filename);
        if (!py_name) {
            Py_INCREF(Py_None);
            py_name = Py_None;
        }
        if (dict_set_owned(dict, "name", py_name) < 0) {
            Py_DECREF(dict);
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            PyBuffer_Release(&buf);
            return NULL;
        }

        unsigned int dos_date = dos_date_from_parts(file->date_y, file->date_m, file->date_d);
        unsigned int dos_time = dos_time_from_parts(file->time_h, file->time_m, file->time_s);
        if (dict_set_owned(dict, "size", PyLong_FromUnsignedLong((unsigned long)file->length)) < 0 ||
            dict_set_owned(dict, "dos_date", PyLong_FromUnsignedLong((unsigned long)dos_date)) < 0 ||
            dict_set_owned(dict, "dos_time", PyLong_FromUnsignedLong((unsigned long)dos_time)) < 0 ||
            dict_set_owned(dict, "attrs", PyLong_FromUnsignedLong((unsigned long)file->attribs)) < 0) {
            Py_DECREF(dict);
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            PyBuffer_Release(&buf);
            return NULL;
        }

        if (dict_set_owned(dict, "date_y", PyLong_FromLong((long)file->date_y)) < 0 ||
            dict_set_owned(dict, "date_m", PyLong_FromLong((long)file->date_m)) < 0 ||
            dict_set_owned(dict, "date_d", PyLong_FromLong((long)file->date_d)) < 0 ||
            dict_set_owned(dict, "time_h", PyLong_FromLong((long)file->time_h)) < 0 ||
            dict_set_owned(dict, "time_m", PyLong_FromLong((long)file->time_m)) < 0 ||
            dict_set_owned(dict, "time_s", PyLong_FromLong((long)file->time_s)) < 0) {
            Py_DECREF(dict);
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            PyBuffer_Release(&buf);
            return NULL;
        }

        if (dict_set_owned(dict, "is_readonly", PyBool_FromLong((file->attribs & MSCAB_ATTRIB_RDONLY) != 0)) < 0 ||
            dict_set_owned(dict, "is_hidden", PyBool_FromLong((file->attribs & MSCAB_ATTRIB_HIDDEN) != 0)) < 0 ||
            dict_set_owned(dict, "is_system", PyBool_FromLong((file->attribs & MSCAB_ATTRIB_SYSTEM) != 0)) < 0 ||
            dict_set_owned(dict, "is_archive", PyBool_FromLong((file->attribs & MSCAB_ATTRIB_ARCH) != 0)) < 0) {
            Py_DECREF(dict);
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            PyBuffer_Release(&buf);
            return NULL;
        }

        int fidx = folder_index(cab->folders, file->folder);
        if (dict_set_owned(dict, "folder_index", PyLong_FromLong(fidx)) < 0 ||
            dict_set_owned(dict, "offset", PyLong_FromLongLong((long long)file->offset)) < 0) {
            Py_DECREF(dict);
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            PyBuffer_Release(&buf);
            return NULL;
        }

        const char *comp = "unknown";
        if (file->folder) {
            comp = compression_name(file->folder->comp_type);
        }
        if (dict_set_owned(dict, "compression", PyUnicode_FromString(comp)) < 0) {
            Py_DECREF(dict);
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            PyBuffer_Release(&buf);
            return NULL;
        }

        if (dict_set_owned(dict, "has_prev", PyBool_FromLong(has_prev)) < 0 ||
            dict_set_owned(dict, "has_next", PyBool_FromLong(has_next)) < 0) {
            Py_DECREF(dict);
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            PyBuffer_Release(&buf);
            return NULL;
        }
        PyObject *py_prev = decode_filename(cab->prevname);
        PyObject *py_next = decode_filename(cab->nextname);
        if (!has_prev) {
            Py_XDECREF(py_prev);
            py_prev = Py_None;
            Py_INCREF(Py_None);
        }
        if (!has_next) {
            Py_XDECREF(py_next);
            py_next = Py_None;
            Py_INCREF(Py_None);
        }
        if (dict_set_owned(dict, "prev_cabinet", py_prev) < 0 ||
            dict_set_owned(dict, "next_cabinet", py_next) < 0) {
            Py_DECREF(dict);
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            PyBuffer_Release(&buf);
            return NULL;
        }

        if (!has_prev && !has_next && cab->set_id == 0 && cab->set_index == 0) {
            Py_INCREF(Py_None);
            if (dict_set_owned(dict, "cabinet_set_id", Py_None) < 0) {
                Py_DECREF(dict);
                Py_DECREF(list);
                cabd->close(cabd, cab);
                cabd_destroy(cabd);
                PyBuffer_Release(&buf);
                return NULL;
            }
            Py_INCREF(Py_None);
            if (dict_set_owned(dict, "cabinet_set_index", Py_None) < 0) {
                Py_DECREF(dict);
                Py_DECREF(list);
                cabd->close(cabd, cab);
                cabd_destroy(cabd);
                PyBuffer_Release(&buf);
                return NULL;
            }
        } else {
            if (dict_set_owned(dict, "cabinet_set_id", PyLong_FromUnsignedLong((unsigned long)cab->set_id)) < 0 ||
                dict_set_owned(dict, "cabinet_set_index", PyLong_FromUnsignedLong((unsigned long)cab->set_index)) < 0) {
                Py_DECREF(dict);
                Py_DECREF(list);
                cabd->close(cabd, cab);
                cabd_destroy(cabd);
                PyBuffer_Release(&buf);
                return NULL;
            }
        }

        if (PyList_Append(list, dict) < 0) {
            Py_DECREF(dict);
            Py_DECREF(list);
            cabd->close(cabd, cab);
            cabd_destroy(cabd);
            PyBuffer_Release(&buf);
            return NULL;
        }
        Py_DECREF(dict);
        file = file->next;
    }

    cabd->close(cabd, cab);
    cabd_destroy(cabd);
    PyBuffer_Release(&buf);

    return Py_BuildValue("Oi", list, MSPACK_ERR_OK);
}

static PyObject *py_cab_extract(PyObject *self, PyObject *args) {
    PyObject *path_obj = NULL;
    PyObject *name_obj = NULL;
    PyObject *out_obj = NULL;
    PyObject *path_bytes = NULL;
    PyObject *name_bytes = NULL;
    PyObject *out_bytes = NULL;

    if (!PyArg_ParseTuple(args, "OOO", &path_obj, &name_obj, &out_obj)) {
        return NULL;
    }
    if (!PyUnicode_FSConverter(path_obj, &path_bytes)) {
        return NULL;
    }
    name_bytes = PyUnicode_AsEncodedString(name_obj, "utf-8", "surrogateescape");
    if (!name_bytes) {
        Py_DECREF(path_bytes);
        return NULL;
    }
    if (!PyUnicode_FSConverter(out_obj, &out_bytes)) {
        Py_DECREF(path_bytes);
        Py_DECREF(name_bytes);
        return NULL;
    }

    const char *path = PyBytes_AS_STRING(path_bytes);
    const char *name = PyBytes_AS_STRING(name_bytes);
    const char *out_path = PyBytes_AS_STRING(out_bytes);

    struct mscab_decompressor *cabd = cabd_create(NULL);
    if (!cabd) {
        Py_DECREF(path_bytes);
        Py_DECREF(name_bytes);
        Py_DECREF(out_bytes);
        return PyLong_FromLong(MSPACK_ERR_NOMEMORY);
    }

    struct mscabd_cabinet *cab = cabd->open(cabd, path);
    if (!cab) {
        int err = cabd->last_error(cabd);
        cabd_destroy(cabd);
        Py_DECREF(path_bytes);
        Py_DECREF(name_bytes);
        Py_DECREF(out_bytes);
        return PyLong_FromLong(err);
    }

    struct mscabd_file *file = cab->files;
    while (file) {
        if (file->filename && strcmp(file->filename, name) == 0) {
            break;
        }
        file = file->next;
    }

    int err = MSPACK_ERR_ARGS;
    if (file) {
        err = cabd->extract(cabd, file, out_path);
    }

    cabd->close(cabd, cab);
    cabd_destroy(cabd);
    Py_DECREF(path_bytes);
    Py_DECREF(name_bytes);
    Py_DECREF(out_bytes);

    return PyLong_FromLong(err);
}

static PyObject *py_cab_extract_bytes(PyObject *self, PyObject *args) {
    Py_buffer buf;
    PyObject *name_obj = NULL;
    PyObject *out_obj = NULL;
    PyObject *name_bytes = NULL;
    PyObject *out_bytes = NULL;

    if (!PyArg_ParseTuple(args, "y*OO", &buf, &name_obj, &out_obj)) {
        return NULL;
    }
    name_bytes = PyUnicode_AsEncodedString(name_obj, "utf-8", "surrogateescape");
    if (!name_bytes) {
        PyBuffer_Release(&buf);
        return NULL;
    }
    if (!PyUnicode_FSConverter(out_obj, &out_bytes)) {
        Py_DECREF(name_bytes);
        PyBuffer_Release(&buf);
        return NULL;
    }

    const char *name = PyBytes_AS_STRING(name_bytes);
    const char *out_path = PyBytes_AS_STRING(out_bytes);

    const char *mem_name = "pylibmspack:memcab";
    struct memcab_system sys;
    memset(&sys, 0, sizeof(sys));
    sys.data = (const unsigned char *)buf.buf;
    sys.size = (size_t)buf.len;
    sys.mem_name = mem_name;
    sys.sys.open = mem_open;
    sys.sys.close = mem_close;
    sys.sys.read = mem_read;
    sys.sys.write = mem_write;
    sys.sys.seek = mem_seek;
    sys.sys.tell = mem_tell;
    sys.sys.message = mem_message;
    sys.sys.alloc = mem_alloc;
    sys.sys.free = mem_free;
    sys.sys.copy = mem_copy;
    sys.sys.null_ptr = NULL;

    struct mscab_decompressor *cabd = cabd_create(&sys.sys);
    if (!cabd) {
        Py_DECREF(name_bytes);
        Py_DECREF(out_bytes);
        PyBuffer_Release(&buf);
        return PyLong_FromLong(MSPACK_ERR_NOMEMORY);
    }

    struct mscabd_cabinet *cab = cabd->open(cabd, mem_name);
    if (!cab) {
        int err = cabd->last_error(cabd);
        cabd_destroy(cabd);
        Py_DECREF(name_bytes);
        Py_DECREF(out_bytes);
        PyBuffer_Release(&buf);
        return PyLong_FromLong(err);
    }

    struct mscabd_file *file = cab->files;
    while (file) {
        if (file->filename && strcmp(file->filename, name) == 0) {
            break;
        }
        file = file->next;
    }

    int err = MSPACK_ERR_ARGS;
    if (file) {
        err = cabd->extract(cabd, file, out_path);
    }

    cabd->close(cabd, cab);
    cabd_destroy(cabd);
    Py_DECREF(name_bytes);
    Py_DECREF(out_bytes);
    PyBuffer_Release(&buf);

    return PyLong_FromLong(err);
}

static PyObject *py_cab_info(PyObject *self, PyObject *args) {
    PyObject *path_obj = NULL;
    PyObject *path_bytes = NULL;
    const char *path = NULL;

    if (!PyArg_ParseTuple(args, "O", &path_obj)) {
        return NULL;
    }
    if (!PyUnicode_FSConverter(path_obj, &path_bytes)) {
        return NULL;
    }
    path = PyBytes_AS_STRING(path_bytes);

    struct mscab_decompressor *cabd = cabd_create(NULL);
    if (!cabd) {
        Py_DECREF(path_bytes);
        return Py_BuildValue("Oi", Py_None, MSPACK_ERR_NOMEMORY);
    }

    struct mscabd_cabinet *cab = cabd->open(cabd, path);
    if (!cab) {
        int err = cabd->last_error(cabd);
        cabd_destroy(cabd);
        Py_DECREF(path_bytes);
        return Py_BuildValue("Oi", Py_None, err);
    }

    PyObject *dict = build_cab_info(cab, NULL);
    if (!dict) {
        cabd->close(cabd, cab);
        cabd_destroy(cabd);
        Py_DECREF(path_bytes);
        return NULL;
    }

    cabd->close(cabd, cab);
    cabd_destroy(cabd);
    Py_DECREF(path_bytes);

    return Py_BuildValue("Oi", dict, MSPACK_ERR_OK);
}

static PyObject *py_cab_info_bytes(PyObject *self, PyObject *args) {
    Py_buffer buf;
    if (!PyArg_ParseTuple(args, "y*", &buf)) {
        return NULL;
    }

    const char *mem_name = "pylibmspack:memcab";
    struct memcab_system sys;
    memset(&sys, 0, sizeof(sys));
    sys.data = (const unsigned char *)buf.buf;
    sys.size = (size_t)buf.len;
    sys.mem_name = mem_name;
    sys.sys.open = mem_open;
    sys.sys.close = mem_close;
    sys.sys.read = mem_read;
    sys.sys.write = mem_write;
    sys.sys.seek = mem_seek;
    sys.sys.tell = mem_tell;
    sys.sys.message = mem_message;
    sys.sys.alloc = mem_alloc;
    sys.sys.free = mem_free;
    sys.sys.copy = mem_copy;
    sys.sys.null_ptr = NULL;

    struct mscab_decompressor *cabd = cabd_create(&sys.sys);
    if (!cabd) {
        PyBuffer_Release(&buf);
        return Py_BuildValue("Oi", Py_None, MSPACK_ERR_NOMEMORY);
    }

    struct mscabd_cabinet *cab = cabd->open(cabd, mem_name);
    if (!cab) {
        int err = cabd->last_error(cabd);
        cabd_destroy(cabd);
        PyBuffer_Release(&buf);
        return Py_BuildValue("Oi", Py_None, err);
    }

    PyObject *dict = build_cab_info(cab, mem_name);
    if (!dict) {
        cabd->close(cabd, cab);
        cabd_destroy(cabd);
        PyBuffer_Release(&buf);
        return NULL;
    }

    cabd->close(cabd, cab);
    cabd_destroy(cabd);
    PyBuffer_Release(&buf);

    return Py_BuildValue("Oi", dict, MSPACK_ERR_OK);
}

static const char *chm_section_name(unsigned int id) {
    switch (id) {
        case 0:
            return "uncompressed";
        case 1:
            return "mscompressed";
        default:
            return "unknown";
    }
}

static PyObject *build_chm_file_dict(struct mschmd_file *file, int is_system) {
    PyObject *dict = PyDict_New();
    if (!dict) return NULL;

    PyObject *py_name = decode_filename(file->filename);
    if (!py_name) {
        Py_INCREF(Py_None);
        py_name = Py_None;
    }
    if (dict_set_owned(dict, "name", py_name) < 0) goto error;
    if (dict_set_owned(dict, "size", PyLong_FromLongLong((long long)file->length)) < 0) goto error;
    if (dict_set_owned(dict, "offset", PyLong_FromLongLong((long long)file->offset)) < 0) goto error;

    long section_id = file->section ? (long)file->section->id : -1;
    if (dict_set_owned(dict, "section_id", PyLong_FromLong(section_id)) < 0) goto error;
    if (dict_set_owned(dict, "section", PyUnicode_FromString(chm_section_name((unsigned int)section_id))) < 0) goto error;
    if (dict_set_owned(dict, "is_system", PyBool_FromLong(is_system)) < 0) goto error;
    return dict;

error:
    Py_DECREF(dict);
    return NULL;
}

static int append_chm_files(PyObject *list, struct mschmd_file *file, int is_system) {
    while (file) {
        PyObject *entry = build_chm_file_dict(file, is_system);
        if (!entry) return -1;
        if (PyList_Append(list, entry) < 0) {
            Py_DECREF(entry);
            return -1;
        }
        Py_DECREF(entry);
        file = file->next;
    }
    return 0;
}

static int count_chm_files(struct mschmd_file *file) {
    int count = 0;
    while (file) {
        count++;
        file = file->next;
    }
    return count;
}

static PyObject *build_chm_info(struct mschmd_header *chm, const char *path) {
    PyObject *dict = PyDict_New();
    if (!dict) return NULL;

    PyObject *py_filename = decode_filename(chm->filename);
    if (path && chm->filename && strcmp(chm->filename, path) == 0) {
        Py_XDECREF(py_filename);
        Py_INCREF(Py_None);
        py_filename = Py_None;
    } else if (!py_filename) {
        Py_INCREF(Py_None);
        py_filename = Py_None;
    }
    if (dict_set_owned(dict, "filename", py_filename) < 0) goto error;

    if (dict_set_owned(dict, "length", PyLong_FromLongLong((long long)chm->length)) < 0) goto error;
    if (dict_set_owned(dict, "version", PyLong_FromUnsignedLong((unsigned long)chm->version)) < 0) goto error;
    if (dict_set_owned(dict, "timestamp", PyLong_FromUnsignedLong((unsigned long)chm->timestamp)) < 0) goto error;
    if (dict_set_owned(dict, "language", PyLong_FromUnsignedLong((unsigned long)chm->language)) < 0) goto error;

    if (dict_set_owned(dict, "dir_offset", PyLong_FromLongLong((long long)chm->dir_offset)) < 0) goto error;
    if (dict_set_owned(dict, "num_chunks", PyLong_FromUnsignedLong((unsigned long)chm->num_chunks)) < 0) goto error;
    if (dict_set_owned(dict, "chunk_size", PyLong_FromUnsignedLong((unsigned long)chm->chunk_size)) < 0) goto error;
    if (dict_set_owned(dict, "density", PyLong_FromUnsignedLong((unsigned long)chm->density)) < 0) goto error;
    if (dict_set_owned(dict, "depth", PyLong_FromUnsignedLong((unsigned long)chm->depth)) < 0) goto error;
    if (dict_set_owned(dict, "index_root", PyLong_FromUnsignedLong((unsigned long)chm->index_root)) < 0) goto error;
    if (dict_set_owned(dict, "first_pmgl", PyLong_FromUnsignedLong((unsigned long)chm->first_pmgl)) < 0) goto error;
    if (dict_set_owned(dict, "last_pmgl", PyLong_FromUnsignedLong((unsigned long)chm->last_pmgl)) < 0) goto error;

    if (dict_set_owned(dict, "files_count", PyLong_FromLong((long)count_chm_files(chm->files))) < 0) goto error;
    if (dict_set_owned(dict, "sysfiles_count", PyLong_FromLong((long)count_chm_files(chm->sysfiles))) < 0) goto error;

    return dict;

error:
    Py_DECREF(dict);
    return NULL;
}

static PyObject *py_chm_list(PyObject *self, PyObject *args) {
    const char *path = NULL;
    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    struct mschm_decompressor *chmd = chmd_create(NULL);
    if (!chmd) {
        Py_INCREF(Py_None);
        return Py_BuildValue("Oi", Py_None, MSPACK_ERR_NOMEMORY);
    }
    struct mschmd_header *chm = chmd->open(chmd, path);
    if (!chm) {
        int err = chmd->last_error(chmd);
        chmd_destroy(chmd);
        Py_INCREF(Py_None);
        return Py_BuildValue("Oi", Py_None, err);
    }

    PyObject *list = PyList_New(0);
    if (!list) {
        chmd->close(chmd, chm);
        chmd_destroy(chmd);
        return NULL;
    }
    if (append_chm_files(list, chm->files, 0) < 0 || append_chm_files(list, chm->sysfiles, 1) < 0) {
        Py_DECREF(list);
        chmd->close(chmd, chm);
        chmd_destroy(chmd);
        return NULL;
    }

    chmd->close(chmd, chm);
    chmd_destroy(chmd);
    return Py_BuildValue("Oi", list, MSPACK_ERR_OK);
}

static PyObject *py_chm_list_bytes(PyObject *self, PyObject *args) {
    Py_buffer buf;
    if (!PyArg_ParseTuple(args, "y*", &buf)) {
        return NULL;
    }

    const char *mem_name = "pylibmspack:memchm";
    struct memcab_system sys;
    memset(&sys, 0, sizeof(sys));
    sys.data = (const unsigned char *)buf.buf;
    sys.size = (size_t)buf.len;
    sys.mem_name = mem_name;
    sys.sys.open = mem_open;
    sys.sys.close = mem_close;
    sys.sys.read = mem_read;
    sys.sys.write = mem_write;
    sys.sys.seek = mem_seek;
    sys.sys.tell = mem_tell;
    sys.sys.message = mem_message;
    sys.sys.alloc = mem_alloc;
    sys.sys.free = mem_free;
    sys.sys.copy = mem_copy;
    sys.sys.null_ptr = NULL;

    struct mschm_decompressor *chmd = chmd_create(&sys.sys);
    if (!chmd) {
        PyBuffer_Release(&buf);
        Py_INCREF(Py_None);
        return Py_BuildValue("Oi", Py_None, MSPACK_ERR_NOMEMORY);
    }
    struct mschmd_header *chm = chmd->open(chmd, mem_name);
    if (!chm) {
        int err = chmd->last_error(chmd);
        chmd_destroy(chmd);
        PyBuffer_Release(&buf);
        Py_INCREF(Py_None);
        return Py_BuildValue("Oi", Py_None, err);
    }

    PyObject *list = PyList_New(0);
    if (!list) {
        chmd->close(chmd, chm);
        chmd_destroy(chmd);
        PyBuffer_Release(&buf);
        return NULL;
    }
    if (append_chm_files(list, chm->files, 0) < 0 || append_chm_files(list, chm->sysfiles, 1) < 0) {
        Py_DECREF(list);
        chmd->close(chmd, chm);
        chmd_destroy(chmd);
        PyBuffer_Release(&buf);
        return NULL;
    }

    chmd->close(chmd, chm);
    chmd_destroy(chmd);
    PyBuffer_Release(&buf);
    return Py_BuildValue("Oi", list, MSPACK_ERR_OK);
}

static PyObject *py_chm_info(PyObject *self, PyObject *args) {
    const char *path = NULL;
    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    struct mschm_decompressor *chmd = chmd_create(NULL);
    if (!chmd) {
        Py_INCREF(Py_None);
        return Py_BuildValue("Oi", Py_None, MSPACK_ERR_NOMEMORY);
    }
    struct mschmd_header *chm = chmd->open(chmd, path);
    if (!chm) {
        int err = chmd->last_error(chmd);
        chmd_destroy(chmd);
        Py_INCREF(Py_None);
        return Py_BuildValue("Oi", Py_None, err);
    }

    PyObject *dict = build_chm_info(chm, path);
    if (!dict) {
        chmd->close(chmd, chm);
        chmd_destroy(chmd);
        return NULL;
    }
    chmd->close(chmd, chm);
    chmd_destroy(chmd);
    return Py_BuildValue("Oi", dict, MSPACK_ERR_OK);
}

static PyObject *py_chm_info_bytes(PyObject *self, PyObject *args) {
    Py_buffer buf;
    if (!PyArg_ParseTuple(args, "y*", &buf)) {
        return NULL;
    }

    const char *mem_name = "pylibmspack:memchm";
    struct memcab_system sys;
    memset(&sys, 0, sizeof(sys));
    sys.data = (const unsigned char *)buf.buf;
    sys.size = (size_t)buf.len;
    sys.mem_name = mem_name;
    sys.sys.open = mem_open;
    sys.sys.close = mem_close;
    sys.sys.read = mem_read;
    sys.sys.write = mem_write;
    sys.sys.seek = mem_seek;
    sys.sys.tell = mem_tell;
    sys.sys.message = mem_message;
    sys.sys.alloc = mem_alloc;
    sys.sys.free = mem_free;
    sys.sys.copy = mem_copy;
    sys.sys.null_ptr = NULL;

    struct mschm_decompressor *chmd = chmd_create(&sys.sys);
    if (!chmd) {
        PyBuffer_Release(&buf);
        Py_INCREF(Py_None);
        return Py_BuildValue("Oi", Py_None, MSPACK_ERR_NOMEMORY);
    }
    struct mschmd_header *chm = chmd->open(chmd, mem_name);
    if (!chm) {
        int err = chmd->last_error(chmd);
        chmd_destroy(chmd);
        PyBuffer_Release(&buf);
        Py_INCREF(Py_None);
        return Py_BuildValue("Oi", Py_None, err);
    }

    PyObject *dict = build_chm_info(chm, mem_name);
    if (!dict) {
        chmd->close(chmd, chm);
        chmd_destroy(chmd);
        PyBuffer_Release(&buf);
        return NULL;
    }
    chmd->close(chmd, chm);
    chmd_destroy(chmd);
    PyBuffer_Release(&buf);
    return Py_BuildValue("Oi", dict, MSPACK_ERR_OK);
}

static const char *skip_chm_slash(const char *name) {
    while (name && name[0] == '/') name++;
    return name;
}

static int chm_name_matches(const char *file_name, const char *query) {
    if (!file_name || !query) return 0;
    if (strcmp(file_name, query) == 0) return 1;
    const char *a = skip_chm_slash(file_name);
    const char *b = skip_chm_slash(query);
    return strcmp(a, b) == 0;
}

static struct mschmd_file *find_chm_file(struct mschmd_header *chm, const char *name) {
    struct mschmd_file *file = chm->files;
    while (file) {
        if (chm_name_matches(file->filename, name)) {
            return file;
        }
        file = file->next;
    }
    file = chm->sysfiles;
    while (file) {
        if (chm_name_matches(file->filename, name)) {
            return file;
        }
        file = file->next;
    }
    return NULL;
}

static PyObject *py_chm_extract(PyObject *self, PyObject *args) {
    const char *path = NULL;
    const char *name = NULL;
    const char *out_path = NULL;
    if (!PyArg_ParseTuple(args, "sss", &path, &name, &out_path)) return NULL;

    struct mschm_decompressor *chmd = chmd_create(NULL);
    if (!chmd) {
        return PyLong_FromLong(MSPACK_ERR_NOMEMORY);
    }
    struct mschmd_header *chm = chmd->open(chmd, path);
    if (!chm) {
        int err = chmd->last_error(chmd);
        chmd_destroy(chmd);
        return PyLong_FromLong(err);
    }

    struct mschmd_file *file = find_chm_file(chm, name);
    if (!file) {
        chmd->close(chmd, chm);
        chmd_destroy(chmd);
        return PyLong_FromLong(MSPACK_ERR_ARGS);
    }

    int err = chmd->extract(chmd, file, out_path);
    if (err != MSPACK_ERR_OK) {
        err = chmd->last_error(chmd);
    }
    chmd->close(chmd, chm);
    chmd_destroy(chmd);
    return PyLong_FromLong(err);
}

static PyObject *py_chm_extract_bytes(PyObject *self, PyObject *args) {
    Py_buffer buf;
    PyObject *name_obj = NULL;
    PyObject *out_obj = NULL;
    PyObject *name_bytes = NULL;
    PyObject *out_bytes = NULL;

    if (!PyArg_ParseTuple(args, "y*OO", &buf, &name_obj, &out_obj)) {
        return NULL;
    }
    name_bytes = PyUnicode_AsEncodedString(name_obj, "utf-8", "surrogateescape");
    if (!name_bytes) {
        PyBuffer_Release(&buf);
        return NULL;
    }
    if (!PyUnicode_FSConverter(out_obj, &out_bytes)) {
        Py_DECREF(name_bytes);
        PyBuffer_Release(&buf);
        return NULL;
    }

    const char *name = PyBytes_AS_STRING(name_bytes);
    const char *out_path = PyBytes_AS_STRING(out_bytes);

    const char *mem_name = "pylibmspack:memchm";
    struct memcab_system sys;
    memset(&sys, 0, sizeof(sys));
    sys.data = (const unsigned char *)buf.buf;
    sys.size = (size_t)buf.len;
    sys.mem_name = mem_name;
    sys.sys.open = mem_open;
    sys.sys.close = mem_close;
    sys.sys.read = mem_read;
    sys.sys.write = mem_write;
    sys.sys.seek = mem_seek;
    sys.sys.tell = mem_tell;
    sys.sys.message = mem_message;
    sys.sys.alloc = mem_alloc;
    sys.sys.free = mem_free;
    sys.sys.copy = mem_copy;
    sys.sys.null_ptr = NULL;

    struct mschm_decompressor *chmd = chmd_create(&sys.sys);
    if (!chmd) {
        Py_DECREF(name_bytes);
        Py_DECREF(out_bytes);
        PyBuffer_Release(&buf);
        return PyLong_FromLong(MSPACK_ERR_NOMEMORY);
    }
    struct mschmd_header *chm = chmd->open(chmd, mem_name);
    if (!chm) {
        int err = chmd->last_error(chmd);
        chmd_destroy(chmd);
        Py_DECREF(name_bytes);
        Py_DECREF(out_bytes);
        PyBuffer_Release(&buf);
        return PyLong_FromLong(err);
    }

    struct mschmd_file *file = find_chm_file(chm, name);
    if (!file) {
        chmd->close(chmd, chm);
        chmd_destroy(chmd);
        Py_DECREF(name_bytes);
        Py_DECREF(out_bytes);
        PyBuffer_Release(&buf);
        return PyLong_FromLong(MSPACK_ERR_ARGS);
    }

    int err = chmd->extract(chmd, file, out_path);
    if (err != MSPACK_ERR_OK) {
        err = chmd->last_error(chmd);
    }
    chmd->close(chmd, chm);
    chmd_destroy(chmd);
    Py_DECREF(name_bytes);
    Py_DECREF(out_bytes);
    PyBuffer_Release(&buf);
    return PyLong_FromLong(err);
}

static const char *szdd_format_name(int fmt) {
    switch (fmt) {
        case MSSZDD_FMT_NORMAL:
            return "normal";
        case MSSZDD_FMT_QBASIC:
            return "qbasic";
        default:
            return "unknown";
    }
}

static PyObject *py_szdd_info(PyObject *self, PyObject *args) {
    const char *path = NULL;
    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    struct msszdd_decompressor *szdd = szddd_create(NULL);
    if (!szdd) {
        Py_INCREF(Py_None);
        return Py_BuildValue("Oi", Py_None, MSPACK_ERR_NOMEMORY);
    }
    struct msszddd_header *hdr = szdd->open(szdd, path);
    if (!hdr) {
        int err = szdd->last_error(szdd);
        szddd_destroy(szdd);
        Py_INCREF(Py_None);
        return Py_BuildValue("Oi", Py_None, err);
    }

    PyObject *dict = PyDict_New();
    if (!dict) {
        szdd->close(szdd, hdr);
        szddd_destroy(szdd);
        return NULL;
    }
    if (dict_set_owned(dict, "format_id", PyLong_FromLong((long)hdr->format)) < 0) goto error;
    if (dict_set_owned(dict, "format", PyUnicode_FromString(szdd_format_name(hdr->format))) < 0) goto error;
    if (dict_set_owned(dict, "length", PyLong_FromLongLong((long long)hdr->length)) < 0) goto error;
    if (dict_set_owned(dict, "missing_char", PyLong_FromLong((long)(unsigned char)hdr->missing_char)) < 0) goto error;

    szdd->close(szdd, hdr);
    szddd_destroy(szdd);
    return Py_BuildValue("Oi", dict, MSPACK_ERR_OK);

error:
    Py_DECREF(dict);
    szdd->close(szdd, hdr);
    szddd_destroy(szdd);
    return NULL;
}

static PyObject *py_szdd_info_bytes(PyObject *self, PyObject *args) {
    Py_buffer buf;
    if (!PyArg_ParseTuple(args, "y*", &buf)) return NULL;

    const char *mem_name = "pylibmspack:memszdd";
    struct memcab_system sys;
    memset(&sys, 0, sizeof(sys));
    sys.data = (const unsigned char *)buf.buf;
    sys.size = (size_t)buf.len;
    sys.mem_name = mem_name;
    sys.sys.open = mem_open;
    sys.sys.close = mem_close;
    sys.sys.read = mem_read;
    sys.sys.write = mem_write;
    sys.sys.seek = mem_seek;
    sys.sys.tell = mem_tell;
    sys.sys.message = mem_message;
    sys.sys.alloc = mem_alloc;
    sys.sys.free = mem_free;
    sys.sys.copy = mem_copy;
    sys.sys.null_ptr = NULL;

    struct msszdd_decompressor *szdd = szddd_create(&sys.sys);
    if (!szdd) {
        PyBuffer_Release(&buf);
        Py_INCREF(Py_None);
        return Py_BuildValue("Oi", Py_None, MSPACK_ERR_NOMEMORY);
    }
    struct msszddd_header *hdr = szdd->open(szdd, mem_name);
    if (!hdr) {
        int err = szdd->last_error(szdd);
        szddd_destroy(szdd);
        PyBuffer_Release(&buf);
        Py_INCREF(Py_None);
        return Py_BuildValue("Oi", Py_None, err);
    }

    PyObject *dict = PyDict_New();
    if (!dict) {
        szdd->close(szdd, hdr);
        szddd_destroy(szdd);
        PyBuffer_Release(&buf);
        return NULL;
    }
    if (dict_set_owned(dict, "format_id", PyLong_FromLong((long)hdr->format)) < 0) goto error;
    if (dict_set_owned(dict, "format", PyUnicode_FromString(szdd_format_name(hdr->format))) < 0) goto error;
    if (dict_set_owned(dict, "length", PyLong_FromLongLong((long long)hdr->length)) < 0) goto error;
    if (dict_set_owned(dict, "missing_char", PyLong_FromLong((long)(unsigned char)hdr->missing_char)) < 0) goto error;

    szdd->close(szdd, hdr);
    szddd_destroy(szdd);
    PyBuffer_Release(&buf);
    return Py_BuildValue("Oi", dict, MSPACK_ERR_OK);

error:
    Py_DECREF(dict);
    szdd->close(szdd, hdr);
    szddd_destroy(szdd);
    PyBuffer_Release(&buf);
    return NULL;
}

static PyObject *py_szdd_extract(PyObject *self, PyObject *args) {
    const char *path = NULL;
    const char *out_path = NULL;
    if (!PyArg_ParseTuple(args, "ss", &path, &out_path)) return NULL;

    struct msszdd_decompressor *szdd = szddd_create(NULL);
    if (!szdd) {
        return PyLong_FromLong(MSPACK_ERR_NOMEMORY);
    }
    struct msszddd_header *hdr = szdd->open(szdd, path);
    if (!hdr) {
        int err = szdd->last_error(szdd);
        szddd_destroy(szdd);
        return PyLong_FromLong(err);
    }

    int err = szdd->extract(szdd, hdr, out_path);
    if (err != MSPACK_ERR_OK) {
        err = szdd->last_error(szdd);
    }
    szdd->close(szdd, hdr);
    szddd_destroy(szdd);
    return PyLong_FromLong(err);
}

static PyObject *py_szdd_extract_bytes(PyObject *self, PyObject *args) {
    Py_buffer buf;
    PyObject *out_obj = NULL;
    PyObject *out_bytes = NULL;
    if (!PyArg_ParseTuple(args, "y*O", &buf, &out_obj)) return NULL;
    if (!PyUnicode_FSConverter(out_obj, &out_bytes)) {
        PyBuffer_Release(&buf);
        return NULL;
    }

    const char *out_path = PyBytes_AS_STRING(out_bytes);
    const char *mem_name = "pylibmspack:memszdd";
    struct memcab_system sys;
    memset(&sys, 0, sizeof(sys));
    sys.data = (const unsigned char *)buf.buf;
    sys.size = (size_t)buf.len;
    sys.mem_name = mem_name;
    sys.sys.open = mem_open;
    sys.sys.close = mem_close;
    sys.sys.read = mem_read;
    sys.sys.write = mem_write;
    sys.sys.seek = mem_seek;
    sys.sys.tell = mem_tell;
    sys.sys.message = mem_message;
    sys.sys.alloc = mem_alloc;
    sys.sys.free = mem_free;
    sys.sys.copy = mem_copy;
    sys.sys.null_ptr = NULL;

    struct msszdd_decompressor *szdd = szddd_create(&sys.sys);
    if (!szdd) {
        Py_DECREF(out_bytes);
        PyBuffer_Release(&buf);
        return PyLong_FromLong(MSPACK_ERR_NOMEMORY);
    }
    struct msszddd_header *hdr = szdd->open(szdd, mem_name);
    if (!hdr) {
        int err = szdd->last_error(szdd);
        szddd_destroy(szdd);
        Py_DECREF(out_bytes);
        PyBuffer_Release(&buf);
        return PyLong_FromLong(err);
    }

    int err = szdd->extract(szdd, hdr, out_path);
    if (err != MSPACK_ERR_OK) {
        err = szdd->last_error(szdd);
    }
    szdd->close(szdd, hdr);
    szddd_destroy(szdd);
    Py_DECREF(out_bytes);
    PyBuffer_Release(&buf);
    return PyLong_FromLong(err);
}

static const char *kwaj_comp_name(unsigned short comp_type) {
    switch (comp_type) {
        case MSKWAJ_COMP_NONE:
            return "none";
        case MSKWAJ_COMP_XOR:
            return "xor";
        case MSKWAJ_COMP_SZDD:
            return "szdd";
        case MSKWAJ_COMP_LZH:
            return "lzh";
        case MSKWAJ_COMP_MSZIP:
            return "mszip";
        default:
            return "unknown";
    }
}

static PyObject *build_kwaj_info(struct mskwajd_header *hdr) {
    PyObject *dict = PyDict_New();
    if (!dict) return NULL;

    if (dict_set_owned(dict, "comp_type", PyLong_FromUnsignedLong((unsigned long)hdr->comp_type)) < 0) goto error;
    if (dict_set_owned(dict, "compression", PyUnicode_FromString(kwaj_comp_name(hdr->comp_type))) < 0) goto error;
    if (dict_set_owned(dict, "data_offset", PyLong_FromLongLong((long long)hdr->data_offset)) < 0) goto error;
    if (dict_set_owned(dict, "headers", PyLong_FromLong((long)hdr->headers)) < 0) goto error;
    if (dict_set_owned(dict, "length", PyLong_FromLongLong((long long)hdr->length)) < 0) goto error;

    PyObject *py_filename = decode_filename(hdr->filename);
    if (!py_filename) {
        Py_INCREF(Py_None);
        py_filename = Py_None;
    }
    if (dict_set_owned(dict, "filename", py_filename) < 0) goto error;

    if (dict_set_owned(dict, "extra_length", PyLong_FromUnsignedLong((unsigned long)hdr->extra_length)) < 0) goto error;
    if (hdr->extra && hdr->extra_length > 0) {
        PyObject *extra = PyBytes_FromStringAndSize(hdr->extra, (Py_ssize_t)hdr->extra_length);
        if (!extra) goto error;
        if (dict_set_owned(dict, "extra", extra) < 0) goto error;
    } else {
        Py_INCREF(Py_None);
        if (dict_set_owned(dict, "extra", Py_None) < 0) goto error;
    }

    int headers = hdr->headers;
    if (dict_set_owned(dict, "has_length", PyBool_FromLong((headers & MSKWAJ_HDR_HASLENGTH) != 0)) < 0) goto error;
    if (dict_set_owned(dict, "has_filename", PyBool_FromLong((headers & MSKWAJ_HDR_HASFILENAME) != 0)) < 0) goto error;
    if (dict_set_owned(dict, "has_fileext", PyBool_FromLong((headers & MSKWAJ_HDR_HASFILEEXT) != 0)) < 0) goto error;
    if (dict_set_owned(dict, "has_extra", PyBool_FromLong((headers & MSKWAJ_HDR_HASEXTRATEXT) != 0)) < 0) goto error;

    return dict;

error:
    Py_DECREF(dict);
    return NULL;
}

static PyObject *py_kwaj_info(PyObject *self, PyObject *args) {
    const char *path = NULL;
    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    struct mskwaj_decompressor *kwaj = kwajd_create(NULL);
    if (!kwaj) {
        Py_INCREF(Py_None);
        return Py_BuildValue("Oi", Py_None, MSPACK_ERR_NOMEMORY);
    }
    struct mskwajd_header *hdr = kwaj->open(kwaj, path);
    if (!hdr) {
        int err = kwaj->last_error(kwaj);
        kwajd_destroy(kwaj);
        Py_INCREF(Py_None);
        return Py_BuildValue("Oi", Py_None, err);
    }

    PyObject *dict = build_kwaj_info(hdr);
    if (!dict) {
        kwaj->close(kwaj, hdr);
        kwajd_destroy(kwaj);
        return NULL;
    }
    kwaj->close(kwaj, hdr);
    kwajd_destroy(kwaj);
    return Py_BuildValue("Oi", dict, MSPACK_ERR_OK);
}

static PyObject *py_kwaj_info_bytes(PyObject *self, PyObject *args) {
    Py_buffer buf;
    if (!PyArg_ParseTuple(args, "y*", &buf)) return NULL;

    const char *mem_name = "pylibmspack:memkwaj";
    struct memcab_system sys;
    memset(&sys, 0, sizeof(sys));
    sys.data = (const unsigned char *)buf.buf;
    sys.size = (size_t)buf.len;
    sys.mem_name = mem_name;
    sys.sys.open = mem_open;
    sys.sys.close = mem_close;
    sys.sys.read = mem_read;
    sys.sys.write = mem_write;
    sys.sys.seek = mem_seek;
    sys.sys.tell = mem_tell;
    sys.sys.message = mem_message;
    sys.sys.alloc = mem_alloc;
    sys.sys.free = mem_free;
    sys.sys.copy = mem_copy;
    sys.sys.null_ptr = NULL;

    struct mskwaj_decompressor *kwaj = kwajd_create(&sys.sys);
    if (!kwaj) {
        PyBuffer_Release(&buf);
        Py_INCREF(Py_None);
        return Py_BuildValue("Oi", Py_None, MSPACK_ERR_NOMEMORY);
    }
    struct mskwajd_header *hdr = kwaj->open(kwaj, mem_name);
    if (!hdr) {
        int err = kwaj->last_error(kwaj);
        kwajd_destroy(kwaj);
        PyBuffer_Release(&buf);
        Py_INCREF(Py_None);
        return Py_BuildValue("Oi", Py_None, err);
    }

    PyObject *dict = build_kwaj_info(hdr);
    if (!dict) {
        kwaj->close(kwaj, hdr);
        kwajd_destroy(kwaj);
        PyBuffer_Release(&buf);
        return NULL;
    }
    kwaj->close(kwaj, hdr);
    kwajd_destroy(kwaj);
    PyBuffer_Release(&buf);
    return Py_BuildValue("Oi", dict, MSPACK_ERR_OK);
}

static PyObject *py_kwaj_extract(PyObject *self, PyObject *args) {
    const char *path = NULL;
    const char *out_path = NULL;
    if (!PyArg_ParseTuple(args, "ss", &path, &out_path)) return NULL;

    struct mskwaj_decompressor *kwaj = kwajd_create(NULL);
    if (!kwaj) {
        return PyLong_FromLong(MSPACK_ERR_NOMEMORY);
    }
    struct mskwajd_header *hdr = kwaj->open(kwaj, path);
    if (!hdr) {
        int err = kwaj->last_error(kwaj);
        kwajd_destroy(kwaj);
        return PyLong_FromLong(err);
    }

    int err = kwaj->extract(kwaj, hdr, out_path);
    if (err != MSPACK_ERR_OK) {
        err = kwaj->last_error(kwaj);
    }
    kwaj->close(kwaj, hdr);
    kwajd_destroy(kwaj);
    return PyLong_FromLong(err);
}

static PyObject *py_kwaj_extract_bytes(PyObject *self, PyObject *args) {
    Py_buffer buf;
    PyObject *out_obj = NULL;
    PyObject *out_bytes = NULL;
    if (!PyArg_ParseTuple(args, "y*O", &buf, &out_obj)) return NULL;
    if (!PyUnicode_FSConverter(out_obj, &out_bytes)) {
        PyBuffer_Release(&buf);
        return NULL;
    }

    const char *out_path = PyBytes_AS_STRING(out_bytes);
    const char *mem_name = "pylibmspack:memkwaj";
    struct memcab_system sys;
    memset(&sys, 0, sizeof(sys));
    sys.data = (const unsigned char *)buf.buf;
    sys.size = (size_t)buf.len;
    sys.mem_name = mem_name;
    sys.sys.open = mem_open;
    sys.sys.close = mem_close;
    sys.sys.read = mem_read;
    sys.sys.write = mem_write;
    sys.sys.seek = mem_seek;
    sys.sys.tell = mem_tell;
    sys.sys.message = mem_message;
    sys.sys.alloc = mem_alloc;
    sys.sys.free = mem_free;
    sys.sys.copy = mem_copy;
    sys.sys.null_ptr = NULL;

    struct mskwaj_decompressor *kwaj = kwajd_create(&sys.sys);
    if (!kwaj) {
        Py_DECREF(out_bytes);
        PyBuffer_Release(&buf);
        return PyLong_FromLong(MSPACK_ERR_NOMEMORY);
    }
    struct mskwajd_header *hdr = kwaj->open(kwaj, mem_name);
    if (!hdr) {
        int err = kwaj->last_error(kwaj);
        kwajd_destroy(kwaj);
        Py_DECREF(out_bytes);
        PyBuffer_Release(&buf);
        return PyLong_FromLong(err);
    }

    int err = kwaj->extract(kwaj, hdr, out_path);
    if (err != MSPACK_ERR_OK) {
        err = kwaj->last_error(kwaj);
    }
    kwaj->close(kwaj, hdr);
    kwajd_destroy(kwaj);
    Py_DECREF(out_bytes);
    PyBuffer_Release(&buf);
    return PyLong_FromLong(err);
}

static PyMethodDef CabMethods[] = {
    {"list_files", py_cab_list, METH_VARARGS, "List files in a CAB"},
    {"list_files_bytes", py_cab_list_bytes, METH_VARARGS, "List files in a CAB from bytes"},
    {"extract_file", py_cab_extract, METH_VARARGS, "Extract a CAB member"},
    {"extract_file_bytes", py_cab_extract_bytes, METH_VARARGS, "Extract a CAB member from bytes"},
    {"cab_info", py_cab_info, METH_VARARGS, "Read CAB header info"},
    {"cab_info_bytes", py_cab_info_bytes, METH_VARARGS, "Read CAB header info from bytes"},
    {"chm_list_files", py_chm_list, METH_VARARGS, "List files in a CHM"},
    {"chm_list_files_bytes", py_chm_list_bytes, METH_VARARGS, "List files in a CHM from bytes"},
    {"chm_extract_file", py_chm_extract, METH_VARARGS, "Extract a CHM member"},
    {"chm_extract_file_bytes", py_chm_extract_bytes, METH_VARARGS, "Extract a CHM member from bytes"},
    {"chm_info", py_chm_info, METH_VARARGS, "Read CHM header info"},
    {"chm_info_bytes", py_chm_info_bytes, METH_VARARGS, "Read CHM header info from bytes"},
    {"szdd_info", py_szdd_info, METH_VARARGS, "Read SZDD header info"},
    {"szdd_info_bytes", py_szdd_info_bytes, METH_VARARGS, "Read SZDD header info from bytes"},
    {"szdd_extract", py_szdd_extract, METH_VARARGS, "Extract SZDD data"},
    {"szdd_extract_bytes", py_szdd_extract_bytes, METH_VARARGS, "Extract SZDD data from bytes"},
    {"kwaj_info", py_kwaj_info, METH_VARARGS, "Read KWAJ header info"},
    {"kwaj_info_bytes", py_kwaj_info_bytes, METH_VARARGS, "Read KWAJ header info from bytes"},
    {"kwaj_extract", py_kwaj_extract, METH_VARARGS, "Extract KWAJ data"},
    {"kwaj_extract_bytes", py_kwaj_extract_bytes, METH_VARARGS, "Extract KWAJ data from bytes"},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef cabmodule = {
    PyModuleDef_HEAD_INIT,
    "_cab",
    NULL,
    -1,
    CabMethods,
};

PyMODINIT_FUNC PyInit__cab(void) {
    PyObject *m = PyModule_Create(&cabmodule);
    if (!m) return NULL;
#ifdef __APPLE__
    Dl_info info;
    if (dladdr((void *)PyInit__cab, &info) == 0 || !info.dli_fname) {
        PyErr_SetString(PyExc_ImportError, "Failed to resolve module path");
        Py_DECREF(m);
        return NULL;
    }
    const char *file_path = info.dli_fname;
    char dylib_path[4096];
    size_t len = strlen(file_path);
    if (len >= sizeof(dylib_path)) {
        PyErr_SetString(PyExc_ImportError, "Module path too long");
        Py_DECREF(m);
        return NULL;
    }
    strncpy(dylib_path, file_path, sizeof(dylib_path));
    dylib_path[sizeof(dylib_path) - 1] = '\0';
    char *slash = strrchr(dylib_path, '/');
    if (!slash) {
        PyErr_SetString(PyExc_ImportError, "Failed to resolve module path");
        Py_DECREF(m);
        return NULL;
    }
    *slash = '\0';
    const char *candidates[] = {
        "/.libs/libmspack.dylib",
        "/.dylibs/libmspack.dylib",
        "/libmspack.dylib",
    };
    int loaded = -1;
    const char *last_err = NULL;
    for (size_t i = 0; i < sizeof(candidates) / sizeof(candidates[0]); i++) {
        strncpy(dylib_path, file_path, sizeof(dylib_path));
        dylib_path[sizeof(dylib_path) - 1] = '\0';
        slash = strrchr(dylib_path, '/');
        if (!slash) break;
        *slash = '\0';
        strncat(dylib_path, candidates[i], sizeof(dylib_path) - strlen(dylib_path) - 1);
        if (ensure_mspack_loaded(dylib_path) == 0) {
            loaded = 0;
            break;
        }
        last_err = dlerror();
    }
    if (loaded != 0) {
        if (!last_err) last_err = "unknown error";
        PyErr_Format(PyExc_ImportError, "Failed to load libmspack.dylib: %s (last path: %s)", last_err, dylib_path);
        Py_DECREF(m);
        return NULL;
    }
#endif
    PyModule_AddIntConstant(m, "MSPACK_ERR_OK", MSPACK_ERR_OK);
    PyModule_AddIntConstant(m, "MSPACK_ERR_ARGS", MSPACK_ERR_ARGS);
    PyModule_AddIntConstant(m, "MSPACK_ERR_OPEN", MSPACK_ERR_OPEN);
    PyModule_AddIntConstant(m, "MSPACK_ERR_READ", MSPACK_ERR_READ);
    PyModule_AddIntConstant(m, "MSPACK_ERR_WRITE", MSPACK_ERR_WRITE);
    PyModule_AddIntConstant(m, "MSPACK_ERR_SEEK", MSPACK_ERR_SEEK);
    PyModule_AddIntConstant(m, "MSPACK_ERR_DATAFORMAT", MSPACK_ERR_DATAFORMAT);
    PyModule_AddIntConstant(m, "MSPACK_ERR_DECRUNCH", MSPACK_ERR_DECRUNCH);
    PyModule_AddIntConstant(m, "MSPACK_ERR_BADCOMP", MSPACK_ERR_BADCOMP);
    PyModule_AddIntConstant(m, "MSPACK_ERR_NOMEMORY", MSPACK_ERR_NOMEMORY);
    PyModule_AddIntConstant(m, "MSPACK_ERR_SIGNATURE", MSPACK_ERR_SIGNATURE);
    PyModule_AddIntConstant(m, "MSPACK_ERR_CHECKSUM", MSPACK_ERR_CHECKSUM);
    return m;
}
