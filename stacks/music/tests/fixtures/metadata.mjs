// LAB ONLY. Loaded in the official Aurral process; upstream source is unchanged.
// External metadata is simulated. Audio, database, private history and APIs are real.
import {appendFileSync} from 'node:fs';
const original = globalThis.fetch;
const ids = ['11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222',
 '33333333-3333-4333-8333-333333333333','44444444-4444-4444-8444-444444444444'];
const names = ['Artista sintético','Artista segundo','Descubrimiento Alice','Descubrimiento Bob'];
const titles = ['Estreno Alice','Estreno Bob'];
const json = body => new Response(JSON.stringify(body),{status:200,headers:{'Content-Type':'application/json'}});
globalThis.fetch = async (input,init={}) => {
 const u=new URL(typeof input==='string'?input:input.url||input);
 if (['music','aurral','localhost','127.0.0.1'].includes(u.hostname)) return original(input,init);
 const headers=new Headers(init.headers);
 const method=(init.method||'GET').toUpperCase();
 if(method!=='GET'||headers.has('authorization')||headers.has('cookie')||init.body) throw new Error('Unexpected private metadata payload');
 const params=Object.fromEntries([...u.searchParams.keys()].filter(k=>k!=="api_key").map(k=>[k,true]));
 const methodName=u.searchParams.get('method');
 if (['artist.getSimilar','artist.getTopTags','artist.getTopTracks','track.getInfo','chart.getTopArtists','chart.getTopTracks','tag.getTopArtists','chart.getTopTags','artist.getInfo'].includes(methodName)) params.method=methodName;
 appendFileSync('/config/lab-metadata-requests.ndjson',JSON.stringify({host:u.hostname,path:u.pathname,method,params,headers:[...headers.keys()]})+'\n');
 if(u.hostname==='ws.audioscrobbler.com') {
  if(u.searchParams.get('api_key')!=='fictional-metadata-key') throw new Error('Real API key forbidden in fixture');
  const kind=u.searchParams.get('method');
  const seed=ids.indexOf(u.searchParams.get('mbid'))>=0?ids.indexOf(u.searchParams.get('mbid')):names.indexOf(u.searchParams.get('artist'));
  if(kind==='artist.getSimilar') {
   const index=seed===1||seed===3?3:2;
   return json({similarartists:{artist:[{name:names[index],mbid:ids[index],match:'0.95'}]}});
  }
  if(kind==='artist.getTopTags') return json({toptags:{tag:[{name:'ambient',count:100}]}});
  if(kind==='artist.getTopTracks') {
   const index=seed===3?1:0;
   return json({toptracks:{track:[{name:titles[index],artist:{name:names[index+2],mbid:ids[index+2]},album:{title:'Pruebas'},playcount:'100'}]}});
  }
  if(kind==='track.getInfo') return json({track:{name:u.searchParams.get('track'),album:{title:'Pruebas'},duration:'34000'}});
  if(kind==='chart.getTopArtists') return json({artists:{artist:[]}});
  if(kind==='chart.getTopTracks') return json({tracks:{track:[]}});
  if(kind==='tag.getTopArtists') return json({topartists:{artist:[]}});
  if(kind==='chart.getTopTags'||kind==='tag.getTopTags') return json({tags:{tag:[{name:'ambient',count:100}]}});
  if(kind==='artist.getInfo') return json({artist:{name:names[Math.max(seed,0)],mbid:ids[Math.max(seed,0)],tags:{tag:[{name:'ambient'}]}}});
  throw new Error('Unsupported Last.fm fixture method: '+kind);
 }
 if(u.hostname==='api.deezer.com') return json({data:[],total:0});
 // A failed metadata enhancement is realistic; it must not block known candidates.
 return new Response('{}',{status:503,headers:{'Content-Type':'application/json'}});
};
