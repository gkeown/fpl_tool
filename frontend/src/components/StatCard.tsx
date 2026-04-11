import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface StatCardProps {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  loading?: boolean;
  className?: string;
}

export default function StatCard({ title, icon, children, loading, className }: StatCardProps) {
  return (
    <Card className={cn("card-stripe overflow-hidden", className)}>
      <CardHeader className="pb-2 pt-4 px-5">
        <CardTitle className="text-xs font-sans font-semibold uppercase tracking-widest text-muted-foreground flex items-center gap-2">
          {icon}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-5 pb-4">
        {loading ? (
          <div className="space-y-3">
            <Skeleton className="h-8 w-24" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        ) : (
          children
        )}
      </CardContent>
    </Card>
  );
}
