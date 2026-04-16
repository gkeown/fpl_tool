import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { getUser, setUser } from "@/lib/auth";
import PageHeader from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, CheckCircle } from "lucide-react";

export default function GuestSetupPage() {
  const navigate = useNavigate();
  const user = getUser();
  const [teamId, setTeamId] = useState(
    user?.fpl_team_id ? String(user.fpl_team_id) : ""
  );
  const [leagueIds, setLeagueIds] = useState(user?.league_ids || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const handleSetup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await api.setup(Number(teamId), leagueIds);
      if (user) {
        setUser({
          ...user,
          fpl_team_id: Number(teamId),
          league_ids: leagueIds,
        });
      }
      setSuccess(true);
      setTimeout(() => navigate("/"), 1000);
    } catch {
      setError("Failed to set up team. Check your team ID and try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <PageHeader title="Setup Your Team" />

      <Card className="card-stripe max-w-lg">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-sans font-semibold uppercase tracking-widest text-muted-foreground">
            FPL Team Setup
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            Enter your FPL team ID and any league IDs you want to track.
            Find your team ID at fantasy.premierleague.com/entry/<strong className="text-foreground">123456</strong>/event/1.
          </p>
          <form onSubmit={handleSetup} className="space-y-4">
            <div>
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-1 block">
                FPL Team ID
              </label>
              <Input
                type="number"
                placeholder="e.g. 1234567"
                value={teamId}
                onChange={(e) => setTeamId(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-1 block">
                League IDs (comma-separated, optional)
              </label>
              <Input
                placeholder="e.g. 620795,929561"
                value={leagueIds}
                onChange={(e) => setLeagueIds(e.target.value)}
              />
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {success && (
              <Alert className="border-fpl-green/30 bg-fpl-green/5">
                <CheckCircle className="h-4 w-4 text-fpl-green" />
                <AlertDescription>
                  Team loaded! Redirecting...
                </AlertDescription>
              </Alert>
            )}

            <Button
              type="submit"
              disabled={!teamId || loading}
              className="w-full bg-fpl-green text-black hover:bg-fpl-green/80 font-semibold"
            >
              {loading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {loading ? "Loading team..." : "Save & Load Team"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
