import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { setToken, setUser } from "@/lib/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Target, Loader2 } from "lucide-react";

export default function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const data: any = await api.login(username.trim(), password);
      setToken(data.token);
      setUser(data.user);

      if (data.user.fpl_team_id === 0) {
        navigate("/setup");
      } else {
        navigate("/");
      }
    } catch {
      setError("Invalid credentials. Check your password or invite code.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="w-full max-w-md card-stripe">
        <CardHeader className="text-center pb-2">
          <div className="flex justify-center mb-3">
            <Target className="h-10 w-10 text-fpl-green" />
          </div>
          <CardTitle className="text-2xl font-display tracking-wider text-fpl-green">
            FPL TRACKER
          </CardTitle>
          <p className="text-sm text-muted-foreground mt-1">
            Sign in to your dashboard
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <Input
                placeholder="Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
              />
            </div>
            <div>
              <Input
                type="password"
                placeholder="Password or invite code"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <Button
              type="submit"
              disabled={!username.trim() || !password || loading}
              className="w-full bg-fpl-green text-black hover:bg-fpl-green/80 font-semibold"
            >
              {loading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Sign In
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
