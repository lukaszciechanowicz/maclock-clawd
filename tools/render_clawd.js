async ({data, pixel}) => {
  const snapshots=[];
  let width,height,fps,animation=null,stage=null;
  if(pixel){
    width=data.w;height=data.h;fps=data.fps;
    const values=Uint8Array.from(data.base,c=>c==='.'?255:Number(c));
    if(values.length!==width*height)throw Error('Invalid pixel base dimensions');
    for(const delta of [null,...data.deltas]){
      if(delta)for(const token of delta.split(',')){
        const index=parseInt(token.slice(0,-1),36),value=token.slice(-1);
        if(index<0||index>=values.length)throw Error('Invalid pixel delta index');
        values[index]=value==='.'?255:Number(value);
      }
      const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
      const ctx=canvas.getContext('2d');
      for(let y=0;y<height;y++)for(let x=0;x<width;x++){
        const value=values[y*width+x];
        if(value!==255){if(!data.palette[value])throw Error('Invalid palette index');ctx.fillStyle=data.palette[value];ctx.fillRect(x,y,1,1);}
      }
      snapshots.push(ctx.getImageData(0,0,width,height));
    }
  }else{
    width=550;height=370;fps=data.fr;
    stage=document.createElement('div');Object.assign(stage.style,{width:width+'px',height:height+'px'});document.body.append(stage);
    animation=window.lottie.loadAnimation({container:stage,renderer:'canvas',loop:false,autoplay:false,animationData:data,rendererSettings:{dpr:1,clearCanvas:true}});
    await new Promise((resolve,reject)=>{
      if(animation.isLoaded)return resolve();
      const timer=setTimeout(()=>reject(Error('Lottie initialization timed out')),10000);
      animation.addEventListener('DOMLoaded',()=>{clearTimeout(timer);resolve();});
      animation.addEventListener('data_failed',()=>{clearTimeout(timer);reject(Error('Lottie data failed'));});
    });
    const canvas=stage.querySelector('canvas');width=canvas.width;height=canvas.height;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});
    for(let frame=0;frame<Math.ceil(data.op-data.ip);frame++){
      animation.goToAndStop(frame,true);
      snapshots.push(ctx.getImageData(0,0,width,height));
    }
  }
  function bounds(image){
    let left=width,top=height,right=-1,bottom=-1;
    for(let y=0;y<height;y++)for(let x=0;x<width;x++)if(image.data[(y*width+x)*4+3]>16){
      left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);
    }
    return right<left?null:{left,right,top,bottom};
  }
  const boxes=snapshots.map(bounds),first=boxes.find(Boolean);
  if(!first)throw Error('Animation has no visible frames');
  const union=boxes.filter(Boolean).reduce((a,b)=>({left:Math.min(a.left,b.left),right:Math.max(a.right,b.right),top:Math.min(a.top,b.top),bottom:Math.max(a.bottom,b.bottom)}));
  const sourceW=union.right-union.left+1,sourceH=union.bottom-union.top+1;
  let scale=Math.min(176/(first.right-first.left+1),350/sourceW,190/sourceH);
  if(pixel)scale=Math.max(1,Math.floor(Math.min(350/sourceW,190/sourceH)));
  const frameW=Math.ceil(sourceW*scale)+4,frameH=Math.ceil(sourceH*scale)+4,columns=Math.min(8,snapshots.length);
  const atlas=document.createElement('canvas');atlas.width=columns*frameW;atlas.height=Math.ceil(snapshots.length/columns)*frameH;
  const ctx=atlas.getContext('2d');ctx.imageSmoothingEnabled=false;
  const source=document.createElement('canvas');source.width=width;source.height=height;
  const sourceCtx=source.getContext('2d');
  for(let frame=0;frame<snapshots.length;frame++){
    sourceCtx.putImageData(snapshots[frame],0,0);
    ctx.drawImage(source,union.left,union.top,sourceW,sourceH,(frame%columns)*frameW+2,Math.floor(frame/columns)*frameH+2,sourceW*scale,sourceH*scale);
  }
  const result={png:atlas.toDataURL('image/png').split(',')[1],fps,frames:snapshots.length,frame_size:[frameW,frameH],columns,offset:[-Math.round(((first.left+first.right)/2-union.left)*scale)-2,-Math.round(sourceH*scale)-2],decoded_bytes:atlas.width*atlas.height*4};
  if(animation)animation.destroy();if(stage)stage.remove();
  return result;
}
