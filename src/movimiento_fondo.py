"""Anima las capas de fondo de las escenas navideñas de LEMC Studio."""
import argparse
import subprocess
from pathlib import Path
import numpy as np
from media import PROCESS_OPTIONS, find_ffmpeg

W, H, FPS = 540, 960, 30


def animate(source, target, ffmpeg, mode):
    common = [str(ffmpeg), '-v', 'error', '-nostdin']
    read = [*common, '-i', str(source), '-an', '-vf', f'scale={W}:{H},fps={FPS}', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-']
    write = [*common, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
             '-i', '-', '-c:v', 'libx264', '-preset', 'fast', '-threads', '3', '-crf', '13',
             '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(target)]
    y,x = np.ogrid[:H,:W]
    if mode=='montañas':
        stills=[]
        for second in (0,5,10,15,20,25,29):
            raw=subprocess.check_output([*common,'-ss',str(second),'-i',str(source),'-vf',f'scale={W}:{H}',
                                         '-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'], **PROCESS_OPTIONS)
            stills.append(np.frombuffer(raw,np.uint8).reshape(H,W,3)[305:601])
        backdrop=np.median(stills,axis=0).astype(np.float32)
        extended=np.pad(backdrop,((0,0),(80,80),(0,0)),mode='reflect')
        mask=(np.clip((y[305:601]-310)/34,0,1)*np.clip((590-y[305:601])/40,0,1))[...,None]
    with subprocess.Popen(read,stdout=subprocess.PIPE, **PROCESS_OPTIONS) as decoder, subprocess.Popen(
            write,stdin=subprocess.PIPE, **PROCESS_OPTIONS) as encoder:
        for index in range(900):
            raw=decoder.stdout.read(W*H*3)
            if len(raw)!=W*H*3:
                raise ValueError('La fuente debe contener 30 segundos completos a 30 fps.')
            frame=np.frombuffer(raw,np.uint8).reshape(H,W,3).copy()
            t=index/FPS
            if mode=='montañas':
                displacement=2.35*t
                left=int(displacement)
                blend=displacement-left
                start=80+left
                shifted=extended[:,start:start+W]*(1-blend)+extended[:,start+1:start+W+1]*blend
                band=frame[305:601]
                # The moving layer covers the landscape while smoke and foreground lights retain their own motion.
                keep=np.clip(1-np.max(np.abs(band.astype(np.float32)-backdrop),axis=2)/82,.04,1)[...,None]
                band[:]=np.clip(band+(shifted-backdrop)*mask*keep,0,255)
            else:
                sky=frame[60:305].astype(np.float32)
                yy=y[60:305]
                q=min(1,t/27)
                zoom=1+.05*q*q*(3-2*q)
                ww,hh=round(W/zoom),round(H/zoom)
                cx=(153-round((W-ww)*.5))*W/ww
                cy=(205-round((H-hh)*.57))*H/hh
                moon_x=91+313*(t/30)
                moon_y=206-53*np.sin(np.pi*t/32)-18*t/30
                core=((x-cx)**2+(yy-cy)**2)**.5
                old_glow=(90/255)*np.exp(-.5*(((x-cx)/(72*zoom))**2+((yy-cy)/(74*zoom))**2))
                sky=np.clip((sky-np.array((177,154,252))*old_glow[...,None])/(1-old_glow[...,None]),0,255)
                wipe=np.clip((60-core)/12,0,1)[...,None]
                outside=(core>90)&((x<75)|(x>264))
                baseline=(sky*outside[...,None]).sum(axis=1)/np.maximum(1,outside.sum(axis=1))[:,None]
                baseline=baseline[:,None,:]
                sky=sky*(1-wipe)+baseline*wipe
                radius=((x-moon_x)**2+(yy-moon_y)**2)**.5
                glow=.36*np.exp(-.5*(radius/57)**2)
                disk=np.clip(40.5-radius,0,1)
                sky=sky*(1-glow[...,None])+np.array((171,145,238))*glow[...,None]
                tint=np.array((228,208,250))+np.clip((moon_y-yy)/15,-3,3)[...,None]
                frame[60:305]=np.clip(sky*(1-disk[...,None])+tint*disk[...,None],0,255)
            encoder.stdin.write(frame.tobytes())
        encoder.stdin.close()
        decoder.stdout.close()
        if encoder.wait():
            raise RuntimeError('Falló la exportación del fondo.')


def command(arguments=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('montañas','luna'))
    parser.add_argument('source',type=Path)
    parser.add_argument('target',type=Path)
    parser.add_argument('--ffmpeg',type=Path)
    args=parser.parse_args(arguments)
    animate(args.source,args.target,args.ffmpeg or find_ffmpeg(),args.mode)


if __name__=='__main__':
    command()
