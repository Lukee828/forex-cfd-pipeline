//+------------------------------------------------------------------+
//|                                               AF_BridgeEA.mq5    |
//|  Alpha Factory — Bridge EA (socket PING, banner discard)         |
//+------------------------------------------------------------------+
#property version   "1.2"
#property strict
input string Bridge_Host="127.0.0.1"; input int Bridge_Port=5005;
input int Connect_Timeout=1500; input int Read_Timeout=1500; input int Ping_Seconds=5;
input string Allowed_Symbols="XAUUSD,US30.cash,GER40.cash";
int g_sock=INVALID_HANDLE; datetime g_lastPing=0;
bool IsSymbolAllowed(const string sym){ string list=Allowed_Symbols; StringTrimLeft(list); StringTrimRight(list);
  string parts[]; int n=StringSplit(list,',',parts);
  for(int i=0;i<n;i++){ string s=parts[i]; StringTrimLeft(s); StringTrimRight(s); if(StringCompare(s,sym,false)==0) return(true); } return(false); }
bool BridgeReadLine(string &o){ o=""; if(g_sock==INVALID_HANDLE||!SocketIsConnected(g_sock)) return(false);
  uchar ch[]; ArrayResize(ch,1); string acc=""; datetime t0=TimeCurrent();
  while(true){ int r=SocketRead(g_sock,ch,1,Read_Timeout); if(r==-1) return(false);
    if(r==0){ if(TimeCurrent()-t0>=(Read_Timeout/1000+1)) return(false); continue; }
    if(ch[0]==\n) break; acc+=CharToString((ushort)ch[0]); } o=acc; return(true); }
bool BridgeConnect(){ if(g_sock!=INVALID_HANDLE){ if(SocketIsConnected(g_sock)) return(true); SocketClose(g_sock); g_sock=INVALID_HANDLE; }
  g_sock=SocketCreate(); if(g_sock==INVALID_HANDLE){ Print("AF_BridgeEA: SocketCreate failed"); return(false); }
  if(!SocketConnect(g_sock,Bridge_Host,Bridge_Port,Connect_Timeout)){
    PrintFormat("AF_BridgeEA: SocketConnect to %s:%d failed (err %d)",Bridge_Host,Bridge_Port,GetLastError());
    SocketClose(g_sock); g_sock=INVALID_HANDLE; return(false); }
  // discard server banner once
  string banner=""; BridgeReadLine(banner);
  PrintFormat("AF_BridgeEA: Connected to %s:%d (banner: %s)",Bridge_Host,Bridge_Port,banner); return(true); }
bool BridgeSendLine(const string line){ if(g_sock==INVALID_HANDLE||!SocketIsConnected(g_sock)){ if(!BridgeConnect()) return(false); }
  string msg=line+"\n"; uchar bytes[]; StringToCharArray(msg,bytes,0,WHOLE_ARRAY,CP_UTF8);
  int sent=SocketSend(g_sock,bytes,ArraySize(bytes)); if(sent!=(int)ArraySize(bytes)){ PrintFormat("AF_BridgeEA: SocketSend incomplete (%d/%d)",sent,ArraySize(bytes)); return(false);} return(true); }
int OnInit(){ const string sym=Symbol(); if(!IsSymbolAllowed(sym)){ PrintFormat("AF_BridgeEA: Symbol %s not allowed. Allowed: %s",sym,Allowed_Symbols); return(INIT_PARAMETERS_INCORRECT); }
  if(!BridgeConnect()){ Print("AF_BridgeEA: initial connect failed; will retry."); } EventSetTimer(1);
  PrintFormat("AF_BridgeEA loaded on %s. Target bridge %s:%d",sym,Bridge_Host,Bridge_Port); return(INIT_SUCCEEDED); }
void OnDeinit(const int r){ EventKillTimer(); if(g_sock!=INVALID_HANDLE){ SocketClose(g_sock); g_sock=INVALID_HANDLE; } Comment(""); Print("AF_BridgeEA deinit."); }
void OnTimer(){ if(TimeCurrent()-g_lastPing<Ping_Seconds) return; g_lastPing=TimeCurrent();
  string status="DISCONNECTED",reply=""; if(g_sock==INVALID_HANDLE||!SocketIsConnected(g_sock)) BridgeConnect();
  if(g_sock!=INVALID_HANDLE&&SocketIsConnected(g_sock)){ status="CONNECTED"; if(BridgeSendLine("PING")){ string r=""; if(BridgeReadLine(r)) reply=r; } }
  Comment(StringFormat("AF_BridgeEA | %s | %s:%d | %s | Reply: %s",Symbol(),Bridge_Host,Bridge_Port,status,reply)); }
void OnTick(){ }
