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
#ifndef MSPACK_ERR_DATAFORMAT
#define MSPACK_ERR_DATAFORMAT 2
#endif
#ifndef MSPACK_ERR_DECRUNCH
#define MSPACK_ERR_DECRUNCH 3
#endif
#ifndef MSPACK_ERR_BADCOMP
#define MSPACK_ERR_BADCOMP 4
#endif
#ifndef MSPACK_ERR_NOMEMORY
#define MSPACK_ERR_NOMEMORY 5
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
static cabd_create_fn g_cabd_create = NULL;
static cabd_destroy_fn g_cabd_destroy = NULL;
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
    if (!g_cabd_create || !g_cabd_destroy) {
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

static PyMethodDef CabMethods[] = {
    {"list_files", py_cab_list, METH_VARARGS, "List files in a CAB"},
    {"list_files_bytes", py_cab_list_bytes, METH_VARARGS, "List files in a CAB from bytes"},
    {"extract_file", py_cab_extract, METH_VARARGS, "Extract a CAB member"},
    {"extract_file_bytes", py_cab_extract_bytes, METH_VARARGS, "Extract a CAB member from bytes"},
    {"cab_info", py_cab_info, METH_VARARGS, "Read CAB header info"},
    {"cab_info_bytes", py_cab_info_bytes, METH_VARARGS, "Read CAB header info from bytes"},
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
    PyModule_AddIntConstant(m, "MSPACK_ERR_DATAFORMAT", MSPACK_ERR_DATAFORMAT);
    PyModule_AddIntConstant(m, "MSPACK_ERR_DECRUNCH", MSPACK_ERR_DECRUNCH);
    PyModule_AddIntConstant(m, "MSPACK_ERR_BADCOMP", MSPACK_ERR_BADCOMP);
    PyModule_AddIntConstant(m, "MSPACK_ERR_NOMEMORY", MSPACK_ERR_NOMEMORY);
    return m;
}
