#include "mspack.h"
#include "lzss.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define FUZZ_TARGET_ALL 0
#define FUZZ_TARGET_CAB 1
#define FUZZ_TARGET_CHM 2
#define FUZZ_TARGET_SZDD 3
#define FUZZ_TARGET_KWAJ 4
#define FUZZ_TARGET_HLP 5
#define FUZZ_TARGET_OAB 6
#define FUZZ_TARGET_OAB_PATCH 7

#ifndef FUZZ_TARGET
#define FUZZ_TARGET FUZZ_TARGET_ALL
#endif

#define MAX_INPUT_SIZE (2 * 1024 * 1024)
#define MAX_OUTPUT_SIZE (1024 * 1024)
#define MAX_EXTRACTS 4

struct fuzz_file {
  struct mspack_file base;
  const uint8_t *data;
  size_t size;
  size_t pos;
  size_t written;
  int writable;
};

struct fuzz_system {
  struct mspack_system sys;
  const uint8_t *input;
  size_t input_size;
  const uint8_t *base;
  size_t base_size;
};

static struct fuzz_file *as_fuzz_file(struct mspack_file *file) {
  return (struct fuzz_file *)file;
}

static struct fuzz_system *as_fuzz_system(struct mspack_system *sys) {
  return (struct fuzz_system *)sys;
}

static struct mspack_file *fuzz_open(struct mspack_system *self, const char *filename, int mode) {
  struct fuzz_system *fs = as_fuzz_system(self);
  struct fuzz_file *file = (struct fuzz_file *)calloc(1, sizeof(*file));
  if (!file) {
    return NULL;
  }

  if (mode == MSPACK_SYS_OPEN_READ) {
    if (filename && strcmp(filename, "base") == 0) {
      file->data = fs->base;
      file->size = fs->base_size;
    }
    else {
      file->data = fs->input;
      file->size = fs->input_size;
    }
  }
  else {
    file->writable = 1;
  }
  return &file->base;
}

static void fuzz_close(struct mspack_file *file) {
  free(file);
}

static int fuzz_read(struct mspack_file *file, void *buffer, int bytes) {
  struct fuzz_file *ff = as_fuzz_file(file);
  size_t available;
  size_t count;

  if (!ff || ff->writable || bytes <= 0) {
    return 0;
  }
  if (ff->pos >= ff->size) {
    return 0;
  }

  available = ff->size - ff->pos;
  count = (size_t)bytes < available ? (size_t)bytes : available;
  memcpy(buffer, ff->data + ff->pos, count);
  ff->pos += count;
  return (int)count;
}

static int fuzz_write(struct mspack_file *file, void *buffer, int bytes) {
  struct fuzz_file *ff = as_fuzz_file(file);
  (void)buffer;

  if (!ff || !ff->writable || bytes <= 0) {
    return -1;
  }
  if ((size_t)bytes > MAX_OUTPUT_SIZE || ff->written > MAX_OUTPUT_SIZE - (size_t)bytes) {
    return -1;
  }
  ff->written += (size_t)bytes;
  ff->pos += (size_t)bytes;
  return bytes;
}

static int fuzz_seek(struct mspack_file *file, off_t offset, int mode) {
  struct fuzz_file *ff = as_fuzz_file(file);
  off_t base;
  off_t next;
  size_t limit;

  if (!ff) {
    return -1;
  }

  if (mode == MSPACK_SYS_SEEK_START) {
    base = 0;
  }
  else if (mode == MSPACK_SYS_SEEK_CUR) {
    base = (off_t)ff->pos;
  }
  else if (mode == MSPACK_SYS_SEEK_END) {
    base = (off_t)(ff->writable ? ff->written : ff->size);
  }
  else {
    return -1;
  }

  next = base + offset;
  limit = ff->writable ? MAX_OUTPUT_SIZE : ff->size;
  if (next < 0 || (uint64_t)next > (uint64_t)limit) {
    return -1;
  }

  ff->pos = (size_t)next;
  if (ff->writable && ff->written < ff->pos) {
    ff->written = ff->pos;
  }
  return 0;
}

static off_t fuzz_tell(struct mspack_file *file) {
  struct fuzz_file *ff = as_fuzz_file(file);
  return ff ? (off_t)ff->pos : (off_t)-1;
}

static void fuzz_message(struct mspack_file *file, const char *format, ...) {
  (void)file;
  (void)format;
}

static void *fuzz_alloc(struct mspack_system *self, size_t bytes) {
  (void)self;
  return calloc(1, bytes);
}

static void fuzz_free(void *ptr) {
  free(ptr);
}

static void fuzz_copy(void *src, void *dest, size_t bytes) {
  memcpy(dest, src, bytes);
}

static void fuzz_system_init(
    struct fuzz_system *fs,
    const uint8_t *input,
    size_t input_size,
    const uint8_t *base,
    size_t base_size) {
  memset(fs, 0, sizeof(*fs));
  fs->input = input;
  fs->input_size = input_size;
  fs->base = base;
  fs->base_size = base_size;
  fs->sys.open = fuzz_open;
  fs->sys.close = fuzz_close;
  fs->sys.read = fuzz_read;
  fs->sys.write = fuzz_write;
  fs->sys.seek = fuzz_seek;
  fs->sys.tell = fuzz_tell;
  fs->sys.message = fuzz_message;
  fs->sys.alloc = fuzz_alloc;
  fs->sys.free = fuzz_free;
  fs->sys.copy = fuzz_copy;
  fs->sys.null_ptr = NULL;
}

static int fuzz_param(const uint8_t *data, size_t size, int minimum, int span, int fallback) {
  if (!data || size == 0 || span <= 0) {
    return fallback;
  }
  return minimum + (int)(data[0] % (uint8_t)span);
}

static void target_cab(const uint8_t *data, size_t size) {
  struct fuzz_system fs;
  struct mscab_decompressor *cabd;
  struct mscabd_cabinet *cab;
  struct mscabd_file *file;
  int count = 0;

  fuzz_system_init(&fs, data, size, NULL, 0);
  cabd = mspack_create_cab_decompressor(&fs.sys);
  if (!cabd) {
    return;
  }
  cabd->set_param(cabd, MSCABD_PARAM_DECOMPBUF, fuzz_param(data, size, 16, 240, 64));
  cabd->set_param(cabd, MSCABD_PARAM_SEARCHBUF, fuzz_param(data, size, 16, 240, 64));

  cab = cabd->open(cabd, "input");
  if (cab) {
    for (file = cab->files; file && count < MAX_EXTRACTS; file = file->next, count++) {
      cabd->extract(cabd, file, "output");
    }
    cabd->close(cabd, cab);
  }

  cab = cabd->search(cabd, "input");
  if (cab) {
    cabd->close(cabd, cab);
  }

  mspack_destroy_cab_decompressor(cabd);
}

static void target_chm(const uint8_t *data, size_t size) {
  struct fuzz_system fs;
  struct mschm_decompressor *chmd;
  struct mschmd_header *chm;
  struct mschmd_file *file;
  int count = 0;

  fuzz_system_init(&fs, data, size, NULL, 0);
  chmd = mspack_create_chm_decompressor(&fs.sys);
  if (!chmd) {
    return;
  }

  chm = chmd->open(chmd, "input");
  if (chm) {
    for (file = chm->files; file && count < MAX_EXTRACTS; file = file->next, count++) {
      chmd->extract(chmd, file, "output");
    }
    for (file = chm->sysfiles; file && count < MAX_EXTRACTS; file = file->next, count++) {
      chmd->extract(chmd, file, "output");
    }
    chmd->close(chmd, chm);
  }

  chm = chmd->fast_open(chmd, "input");
  if (chm) {
    struct mschmd_file found;
    memset(&found, 0, sizeof(found));
    if (chmd->fast_find(chmd, chm, "/index.html", &found, sizeof(found)) == MSPACK_ERR_OK) {
      chmd->extract(chmd, &found, "output");
    }
    chmd->close(chmd, chm);
  }

  mspack_destroy_chm_decompressor(chmd);
}

static void target_szdd(const uint8_t *data, size_t size) {
  struct fuzz_system fs;
  struct msszdd_decompressor *szdd;
  struct msszddd_header *hdr;

  fuzz_system_init(&fs, data, size, NULL, 0);
  szdd = mspack_create_szdd_decompressor(&fs.sys);
  if (!szdd) {
    return;
  }

  hdr = szdd->open(szdd, "input");
  if (hdr) {
    szdd->extract(szdd, hdr, "output");
    szdd->close(szdd, hdr);
  }
  szdd->decompress(szdd, "input", "output");
  mspack_destroy_szdd_decompressor(szdd);
}

static void target_kwaj(const uint8_t *data, size_t size) {
  struct fuzz_system fs;
  struct mskwaj_decompressor *kwaj;
  struct mskwajd_header *hdr;

  fuzz_system_init(&fs, data, size, NULL, 0);
  kwaj = mspack_create_kwaj_decompressor(&fs.sys);
  if (!kwaj) {
    return;
  }

  hdr = kwaj->open(kwaj, "input");
  if (hdr) {
    kwaj->extract(kwaj, hdr, "output");
    kwaj->close(kwaj, hdr);
  }
  kwaj->decompress(kwaj, "input", "output");
  mspack_destroy_kwaj_decompressor(kwaj);
}

static void target_hlp(const uint8_t *data, size_t size) {
  struct fuzz_system fs;
  struct mspack_file *input;
  struct mspack_file *output;
  int mode = LZSS_MODE_MSHELP;

  if (size > 0) {
    mode = (int)(data[0] % 3);
    data++;
    size--;
  }

  fuzz_system_init(&fs, data, size, NULL, 0);
  input = fs.sys.open(&fs.sys, "input", MSPACK_SYS_OPEN_READ);
  output = fs.sys.open(&fs.sys, "output", MSPACK_SYS_OPEN_WRITE);
  if (input && output) {
    lzss_decompress(&fs.sys, input, output, 64, mode);
  }
  if (input) {
    fs.sys.close(input);
  }
  if (output) {
    fs.sys.close(output);
  }
}

static void target_oab(const uint8_t *data, size_t size) {
  struct fuzz_system fs;
  struct msoab_decompressor *oab;

  fuzz_system_init(&fs, data, size, NULL, 0);
  oab = mspack_create_oab_decompressor(&fs.sys);
  if (!oab) {
    return;
  }
  oab->set_param(oab, MSOABD_PARAM_DECOMPBUF, fuzz_param(data, size, 16, 240, 64));
  oab->decompress(oab, "input", "output");
  mspack_destroy_oab_decompressor(oab);
}

static void target_oab_patch(const uint8_t *data, size_t size) {
  struct fuzz_system fs;
  struct msoab_decompressor *oab;
  size_t split = size / 2;

  fuzz_system_init(&fs, data, split, data + split, size - split);
  oab = mspack_create_oab_decompressor(&fs.sys);
  if (!oab) {
    return;
  }
  oab->set_param(oab, MSOABD_PARAM_DECOMPBUF, fuzz_param(data, size, 16, 240, 64));
  oab->decompress_incremental(oab, "input", "base", "output");
  mspack_destroy_oab_decompressor(oab);
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
  int selftest = MSPACK_ERR_OK;
  if (size > MAX_INPUT_SIZE) {
    return 0;
  }
  MSPACK_SYS_SELFTEST(selftest);
  if (selftest != MSPACK_ERR_OK) {
    return 0;
  }

#if FUZZ_TARGET == FUZZ_TARGET_CAB
  target_cab(data, size);
#elif FUZZ_TARGET == FUZZ_TARGET_CHM
  target_chm(data, size);
#elif FUZZ_TARGET == FUZZ_TARGET_SZDD
  target_szdd(data, size);
#elif FUZZ_TARGET == FUZZ_TARGET_KWAJ
  target_kwaj(data, size);
#elif FUZZ_TARGET == FUZZ_TARGET_HLP
  target_hlp(data, size);
#elif FUZZ_TARGET == FUZZ_TARGET_OAB
  target_oab(data, size);
#elif FUZZ_TARGET == FUZZ_TARGET_OAB_PATCH
  target_oab_patch(data, size);
#else
  if (size == 0) {
    target_cab(data, size);
  }
  else {
    const uint8_t selector = data[0] % 7;
    data++;
    size--;
    switch (selector) {
      case 0:
        target_cab(data, size);
        break;
      case 1:
        target_chm(data, size);
        break;
      case 2:
        target_szdd(data, size);
        break;
      case 3:
        target_kwaj(data, size);
        break;
      case 4:
        target_hlp(data, size);
        break;
      case 5:
        target_oab(data, size);
        break;
      default:
        target_oab_patch(data, size);
        break;
    }
  }
#endif
  return 0;
}
