interface HeaderProps {
  matchId: number;
  onMatchIdChange: (id: number) => void;
  isLive: boolean;
  isRefreshing: boolean;
  lastUpdated: Date | null;
}

export function Header({
  matchId,
  onMatchIdChange,
  isLive,
  isRefreshing,
  lastUpdated,
}: HeaderProps) {
  return (
    <header className="border-b border-pitch-700/80 bg-pitch-900/60 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/15 ring-1 ring-accent/30">
            <span className="text-lg font-bold text-accent">CB</span>
          </div>
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-white sm:text-xl">
              CricBuzz Live
            </h1>
            <p className="text-xs text-slate-400">Match Tracker</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-400">
            Match ID
            <input
              type="number"
              min={1}
              value={matchId}
              onChange={(e) => onMatchIdChange(Number(e.target.value) || 1)}
              className="w-20 rounded-lg border border-pitch-700 bg-pitch-800 px-3 py-1.5 font-mono text-sm text-white outline-none ring-accent/50 focus:ring-2"
            />
          </label>

          <div className="flex items-center gap-2 rounded-full border border-pitch-700 bg-pitch-800/80 px-3 py-1.5 text-xs">
            {isLive && (
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
              </span>
            )}
            <span className={isLive ? "text-accent" : "text-slate-400"}>
              {isLive ? "LIVE" : " E}
            </span>
            {isRefreshing && (
              <span className="text-slate-500">· updating</span>
            )}
            {lastUpdated && !isRefreshing && (
              <span className="text-slate-500">
                · {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
