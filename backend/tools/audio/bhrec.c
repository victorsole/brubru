// Record a CoreAudio input device (by name) to stdout as raw float32 interleaved PCM.
// Uses an AudioQueue with its own buffer pool, so every captured block is delivered
// to the callback -- unlike ffmpeg's avfoundation demuxer, which keeps a single
// pending buffer and silently drops blocks that arrive before it is read.
#include <AudioToolbox/AudioToolbox.h>
#include <CoreAudio/CoreAudio.h>
#include <signal.h>
#include <stdio.h>
#include <unistd.h>

static volatile sig_atomic_t running = 1;
static void on_sig(int s){ (void)s; running = 0; }

static void cb(void *ud, AudioQueueRef q, AudioQueueBufferRef b, const AudioTimeStamp *t,
               UInt32 n, const AudioStreamPacketDescription *d){
    (void)ud;(void)t;(void)n;(void)d;
    if (b->mAudioDataByteSize) {
        size_t w = fwrite(b->mAudioData, 1, b->mAudioDataByteSize, stdout);
        if (w != b->mAudioDataByteSize) running = 0;   // downstream closed
    }
    if (running) AudioQueueEnqueueBuffer(q, b, 0, NULL);
}

static CFStringRef find_uid(const char *want){
    AudioObjectPropertyAddress da={kAudioHardwarePropertyDevices,kAudioObjectPropertyScopeGlobal,kAudioObjectPropertyElementMain};
    UInt32 sz=0; AudioObjectGetPropertyDataSize(kAudioObjectSystemObject,&da,0,NULL,&sz);
    int n=sz/sizeof(AudioObjectID); AudioObjectID *ids=malloc(sz);
    AudioObjectGetPropertyData(kAudioObjectSystemObject,&da,0,NULL,&sz,ids);
    CFStringRef w=CFStringCreateWithCString(NULL,want,kCFStringEncodingUTF8);
    for(int i=0;i<n;i++){
        AudioObjectPropertyAddress na={kAudioObjectPropertyName,kAudioObjectPropertyScopeGlobal,kAudioObjectPropertyElementMain};
        CFStringRef nm=NULL; UInt32 s=sizeof(nm);
        if(AudioObjectGetPropertyData(ids[i],&na,0,NULL,&s,&nm)!=noErr||!nm) continue;
        AudioObjectPropertyAddress ic={kAudioDevicePropertyStreamConfiguration,kAudioObjectPropertyScopeInput,kAudioObjectPropertyElementMain};
        UInt32 isz=0; if(AudioObjectGetPropertyDataSize(ids[i],&ic,0,NULL,&isz)!=noErr||isz<=sizeof(UInt32)) continue;
        if(CFStringFind(nm,w,kCFCompareCaseInsensitive).location==kCFNotFound) continue;
        AudioObjectPropertyAddress ua={kAudioDevicePropertyDeviceUID,kAudioObjectPropertyScopeGlobal,kAudioObjectPropertyElementMain};
        CFStringRef uid=NULL; s=sizeof(uid);
        if(AudioObjectGetPropertyData(ids[i],&ua,0,NULL,&s,&uid)==noErr) return uid;
    }
    return NULL;
}

int main(int argc,char**argv){
    const char *dev = argc>1 ? argv[1] : "BlackHole 2ch";
    double rate = argc>2 ? atof(argv[2]) : 48000.0;
    CFStringRef uid = find_uid(dev);
    if(!uid){ fprintf(stderr,"[ERROR] no input device matching '%s'\n",dev); return 2; }
    signal(SIGINT,on_sig); signal(SIGTERM,on_sig); signal(SIGPIPE,on_sig);
    setvbuf(stdout,NULL,_IOFBF,1<<20);

    AudioStreamBasicDescription f={0};
    f.mSampleRate=rate; f.mFormatID=kAudioFormatLinearPCM;
    f.mFormatFlags=kAudioFormatFlagIsFloat|kAudioFormatFlagIsPacked;
    f.mChannelsPerFrame=2; f.mBitsPerChannel=32; f.mBytesPerFrame=8; f.mFramesPerPacket=1; f.mBytesPerPacket=8;

    AudioQueueRef q; OSStatus st=AudioQueueNewInput(&f,cb,NULL,CFRunLoopGetCurrent(),kCFRunLoopCommonModes,0,&q);
    if(st){ fprintf(stderr,"[ERROR] AudioQueueNewInput %d\n",(int)st); return 3; }
    st=AudioQueueSetProperty(q,kAudioQueueProperty_CurrentDevice,&uid,sizeof(uid));
    if(st){ fprintf(stderr,"[ERROR] select device %d\n",(int)st); return 4; }
    for(int i=0;i<8;i++){ AudioQueueBufferRef b; AudioQueueAllocateBuffer(q,(UInt32)(rate*0.1)*8,&b); AudioQueueEnqueueBuffer(q,b,0,NULL); }
    st=AudioQueueStart(q,NULL);
    if(st){ fprintf(stderr,"[ERROR] start %d\n",(int)st); return 5; }
    fprintf(stderr,"[bhrec] recording '%s' at %.0f Hz, float32 stereo -> stdout\n",dev,rate);
    while(running) CFRunLoopRunInMode(kCFRunLoopDefaultMode,0.25,false);
    AudioQueueStop(q,true); AudioQueueDispose(q,true); fflush(stdout);
    fprintf(stderr,"[bhrec] stopped\n");
    return 0;
}
