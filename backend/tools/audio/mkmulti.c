// Create a macOS MULTI-OUTPUT device (real output + BlackHole) and select it.
// CoreAudio is a C API, so this avoids the Swift/SDK mismatch entirely.
#include <CoreAudio/CoreAudio.h>
#include <CoreFoundation/CoreFoundation.h>
#include <stdio.h>
#include <string.h>

static CFStringRef str_prop(AudioObjectID id, AudioObjectPropertySelector sel) {
    AudioObjectPropertyAddress a = {sel, kAudioObjectPropertyScopeGlobal, kAudioObjectPropertyElementMain};
    CFStringRef out = NULL; UInt32 sz = sizeof(out);
    if (AudioObjectGetPropertyData(id, &a, 0, NULL, &sz, &out) != noErr) return NULL;
    return out;
}
static int out_channels(AudioObjectID id) {
    AudioObjectPropertyAddress a = {kAudioDevicePropertyStreamConfiguration,
                                    kAudioObjectPropertyScopeOutput, kAudioObjectPropertyElementMain};
    UInt32 sz = 0;
    if (AudioObjectGetPropertyDataSize(id, &a, 0, NULL, &sz) != noErr || sz == 0) return 0;
    AudioBufferList *bl = (AudioBufferList *)malloc(sz);
    int n = 0;
    if (AudioObjectGetPropertyData(id, &a, 0, NULL, &sz, bl) == noErr)
        for (UInt32 i = 0; i < bl->mNumberBuffers; i++) n += bl->mBuffers[i].mNumberChannels;
    free(bl);
    return n;
}
static char *cstr(CFStringRef s, char *buf, size_t n) {
    if (!s) { buf[0] = 0; return buf; }
    CFStringGetCString(s, buf, n, kCFStringEncodingUTF8);
    return buf;
}

int main(int argc, char **argv) {
    const char *want = (argc > 1) ? argv[1] : "MacBook Pro Speakers";
    // Optional second argument "only": build the device from the named output and
    // BlackHole alone, so listening on earphones does not also play through the speakers.
    int only = (argc > 2) && strcmp(argv[2], "only") == 0;
    AudioObjectPropertyAddress da = {kAudioHardwarePropertyDevices,
                                     kAudioObjectPropertyScopeGlobal, kAudioObjectPropertyElementMain};
    UInt32 sz = 0;
    AudioObjectGetPropertyDataSize(kAudioObjectSystemObject, &da, 0, NULL, &sz);
    int ndev = sz / sizeof(AudioObjectID);
    AudioObjectID *ids = malloc(sz);
    AudioObjectGetPropertyData(kAudioObjectSystemObject, &da, 0, NULL, &sz, ids);

    CFStringRef speakersUID = NULL, blackholeUID = NULL;
    CFStringRef realUID[8]; char realName[8][256]; int nReal = 0;
    char sName[256] = "", bName[256] = "", tmp[256];
    const CFStringRef TARGET = CFSTR("com.brubru.capture.multi");
    AudioObjectID existing = 0;

    for (int i = 0; i < ndev; i++) {
        CFStringRef uid = str_prop(ids[i], kAudioDevicePropertyDeviceUID);
        if (uid && CFStringCompare(uid, TARGET, 0) == kCFCompareEqualTo) { existing = ids[i]; continue; }
        if (out_channels(ids[i]) <= 0) continue;
        CFStringRef nm = str_prop(ids[i], kAudioObjectPropertyName);
        if (!nm || !uid) continue;
        if (CFStringFind(nm, CFSTR("BlackHole"), kCFCompareCaseInsensitive).location != kCFNotFound) {
            blackholeUID = CFRetain(uid); cstr(nm, bName, sizeof bName);
        } else if (CFStringFind(nm, CFSTR("Brubru"), kCFCompareCaseInsensitive).location == kCFNotFound) {
            // Collect EVERY real output, not just the first one found: picking
            // the first sent audio to a monitor the user was not listening on.
            if (nReal < 8) { realUID[nReal] = CFRetain(uid); cstr(nm, realName[nReal], 256); nReal++; }
            CFStringRef w = CFStringCreateWithCString(NULL, want, kCFStringEncodingUTF8);
            if (CFStringFind(nm, w, kCFCompareCaseInsensitive).location != kCFNotFound) {
                speakersUID = CFRetain(uid); cstr(nm, sName, sizeof sName);
            }
            CFRelease(w);
        }
    }
    if (!speakersUID && nReal > 0) { speakersUID = realUID[0]; snprintf(sName, sizeof sName, "%s", realName[0]);
        fprintf(stderr, "[WARN] '%s' not found; using %s as master\n", want, sName); }
    if (!speakersUID || !blackholeUID) {
        fprintf(stderr, "[ERROR] need a real output AND BlackHole (speakers=%s blackhole=%s)\n",
                speakersUID ? sName : "nil", blackholeUID ? bName : "nil");
        return 2;
    }
    printf("[info] real output : %s\n", sName);
    printf("[info] loopback    : %s\n", bName);

    AudioObjectID dev = existing;
    if (!existing) {
        // kAudioAggregateDeviceIsStackedKey=1 makes this a MULTI-OUTPUT device
        // (identical audio to every sub-device), not a plain aggregate.
        // The real output is the main sub-device and therefore the clock master,
        // so drift compensation goes on BlackHole ONLY.
        int one = 1, zero = 0;
        CFNumberRef cf_one = CFNumberCreate(NULL, kCFNumberIntType, &one);
        CFNumberRef cf_zero = CFNumberCreate(NULL, kCFNumberIntType, &zero);

        const void *sk[] = {CFSTR(kAudioSubDeviceUIDKey), CFSTR(kAudioSubDeviceDriftCompensationKey)};
        const void *sv[] = {speakersUID, cf_zero};
        CFDictionaryRef subS = CFDictionaryCreate(NULL, sk, sv, 2,
            &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
        const void *bv[] = {blackholeUID, cf_one};
        CFDictionaryRef subB = CFDictionaryCreate(NULL, sk, bv, 2,
            &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
        const void *subs[10]; int nSub = 0;
        subs[nSub++] = subS;                       // the master, first
        for (int i = 0; !only && i < nReal && nSub < 9; i++) {
            if (CFStringCompare(realUID[i], speakersUID, 0) == kCFCompareEqualTo) continue;
            const void *ov[] = {realUID[i], cf_one};   // drift-corrected, not master
            subs[nSub++] = CFDictionaryCreate(NULL, sk, ov, 2,
                &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
            printf("[info] also feeding: %s\n", realName[i]);
        }
        subs[nSub++] = subB;
        CFArrayRef list = CFArrayCreate(NULL, subs, nSub, &kCFTypeArrayCallBacks);

        const void *k[] = {CFSTR(kAudioAggregateDeviceNameKey), CFSTR(kAudioAggregateDeviceUIDKey),
                           CFSTR(kAudioAggregateDeviceIsStackedKey), CFSTR(kAudioAggregateDeviceMainSubDeviceKey),
                           CFSTR(kAudioAggregateDeviceSubDeviceListKey)};
        const void *v[] = {CFSTR("Brubru Capture (Multi-Output)"), TARGET, cf_one, speakersUID, list};
        CFDictionaryRef desc = CFDictionaryCreate(NULL, k, v, 5,
            &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);

        OSStatus st = AudioHardwareCreateAggregateDevice(desc, &dev);
        if (st != noErr || !dev) { fprintf(stderr, "[ERROR] create failed, OSStatus %d\n", (int)st); return 3; }
        printf("[ok] created 'Brubru Capture (Multi-Output)' id=%u\n", (unsigned)dev);
    } else {
        printf("[ok] reusing existing multi-output device id=%u\n", (unsigned)existing);
    }

    AudioObjectPropertyAddress oa = {kAudioHardwarePropertyDefaultOutputDevice,
                                     kAudioObjectPropertyScopeGlobal, kAudioObjectPropertyElementMain};
    OSStatus st2 = AudioObjectSetPropertyData(kAudioObjectSystemObject, &oa, 0, NULL, sizeof(dev), &dev);
    if (st2 != noErr) { fprintf(stderr, "[WARN] could not set default output, OSStatus %d\n", (int)st2); return 4; }
    printf("[ok] default output switched. You still hear %s; BlackHole now gets a copy.\n", sName);
    (void)tmp;
    return 0;
}
