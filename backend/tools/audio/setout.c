// Set the default output device by (case-insensitive substring of its) name.
#include <CoreAudio/CoreAudio.h>
#include <stdio.h>
static CFStringRef sp(AudioObjectID id, AudioObjectPropertySelector sel){AudioObjectPropertyAddress a={sel,kAudioObjectPropertyScopeGlobal,kAudioObjectPropertyElementMain};CFStringRef o=NULL;UInt32 s=sizeof(o);return AudioObjectGetPropertyData(id,&a,0,NULL,&s,&o)==noErr?o:NULL;}
static int outch(AudioObjectID id){AudioObjectPropertyAddress a={kAudioDevicePropertyStreamConfiguration,kAudioObjectPropertyScopeOutput,kAudioObjectPropertyElementMain};UInt32 sz=0;if(AudioObjectGetPropertyDataSize(id,&a,0,NULL,&sz)!=noErr||!sz)return 0;AudioBufferList*b=malloc(sz);int n=0;if(AudioObjectGetPropertyData(id,&a,0,NULL,&sz,b)==noErr)for(UInt32 i=0;i<b->mNumberBuffers;i++)n+=b->mBuffers[i].mNumberChannels;free(b);return n;}
int main(int argc,char**argv){
  if(argc<2){fprintf(stderr,"usage: setout <device name>\n");return 1;}
  CFStringRef want=CFStringCreateWithCString(NULL,argv[1],kCFStringEncodingUTF8);
  AudioObjectPropertyAddress da={kAudioHardwarePropertyDevices,kAudioObjectPropertyScopeGlobal,kAudioObjectPropertyElementMain};
  UInt32 sz=0;AudioObjectGetPropertyDataSize(kAudioObjectSystemObject,&da,0,NULL,&sz);int n=sz/sizeof(AudioObjectID);
  AudioObjectID*ids=malloc(sz);AudioObjectGetPropertyData(kAudioObjectSystemObject,&da,0,NULL,&sz,ids);
  for(int i=0;i<n;i++){
    if(outch(ids[i])<=0)continue; CFStringRef nm=sp(ids[i],kAudioObjectPropertyName); if(!nm)continue;
    if(CFStringFind(nm,want,kCFCompareCaseInsensitive).location==kCFNotFound)continue;
    AudioObjectPropertyAddress oa={kAudioHardwarePropertyDefaultOutputDevice,kAudioObjectPropertyScopeGlobal,kAudioObjectPropertyElementMain};
    AudioObjectID d=ids[i]; OSStatus st=AudioObjectSetPropertyData(kAudioObjectSystemObject,&oa,0,NULL,sizeof(d),&d);
    char buf[256];CFStringGetCString(nm,buf,sizeof buf,kCFStringEncodingUTF8);
    printf(st==noErr?"[ok] default output -> %s\n":"[ERROR] could not select %s\n",buf); return st!=noErr;
  }
  fprintf(stderr,"[ERROR] no output device matching '%s'\n",argv[1]);return 2;}
