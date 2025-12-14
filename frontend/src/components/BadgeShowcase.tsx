import { useEffect, useMemo, useState } from 'react';
import { ArrowClockwise, Clock, Medal, Sparkle } from '@phosphor-icons/react';
import { apiClient, Badge, BadgeStats } from '../lib/apiClient';

interface BadgeShowcaseProps {
  userId?: number;
  isOwnProfile?: boolean;
}

const TYPE_STYLES: Record<
  string,
  { bg: string; border: string; accent: string }
> = {
  recipes: {
    bg: 'linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(59, 130, 246, 0.08))',
    border: 'rgba(16, 185, 129, 0.35)',
    accent: '#22d3ee',
  },
  likes: {
    bg: 'linear-gradient(135deg, rgba(239, 68, 68, 0.16), rgba(245, 158, 11, 0.08))',
    border: 'rgba(239, 68, 68, 0.35)',
    accent: '#fb7185',
  },
  posts: {
    bg: 'linear-gradient(135deg, rgba(124, 58, 237, 0.16), rgba(59, 130, 246, 0.1))',
    border: 'rgba(124, 58, 237, 0.35)',
    accent: '#a78bfa',
  },
  default: {
    bg: 'linear-gradient(135deg, rgba(99, 102, 241, 0.12), rgba(14, 165, 233, 0.08))',
    border: 'rgba(99, 102, 241, 0.35)',
    accent: '#38bdf8',
  },
};

const TYPE_LABELS: Record<string, string> = {
  recipes: 'Recipes',
  likes: 'Likes',
  posts: 'Posts',
};

const formatDate = (value?: string | null) => {
  if (!value) return 'Not calculated yet';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
};

const BadgeShowcase = ({ userId, isOwnProfile = false }: BadgeShowcaseProps) => {
  const [badges, setBadges] = useState<Badge[]>([]);
  const [stats, setStats] = useState<BadgeStats | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [recalculating, setRecalculating] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [message, setMessage] = useState<string>('');

  const loadBadges = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await apiClient.getUserBadges(userId);
      setBadges(data.badges || []);
      setStats(data.stats);
      setLastUpdated(data.badges_updated_at || null);
    } catch (err: any) {
      console.error('Failed to load badges:', err);
      setError('Failed to load badges. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBadges();
  }, [userId]);

  const handleRecalculate = async () => {
    setRecalculating(true);
    setMessage('');
    setError('');
    try {
      await apiClient.recalculateBadges();
      setMessage('Badges recalculated. Syncing latest results...');
      await loadBadges();
    } catch (err: any) {
      console.error('Failed to recalculate badges:', err);
      setError('Could not recalculate badges right now.');
    } finally {
      setRecalculating(false);
    }
  };

  const sortedBadges = useMemo(() => {
    const typeOrder: Record<string, number> = { recipes: 0, likes: 1, posts: 2 };
    return [...badges].sort((a, b) => {
      const typeDiff = (typeOrder[a.type] ?? 3) - (typeOrder[b.type] ?? 3);
      if (typeDiff !== 0) return typeDiff;
      const thresholdDiff = (a.threshold ?? 0) - (b.threshold ?? 0);
      if (thresholdDiff !== 0) return thresholdDiff;
      return a.name.localeCompare(b.name);
    });
  }, [badges]);

  const statBlocks = [
    { key: 'recipes', label: 'Recipes Posted', value: stats?.recipe_count ?? 0 },
    { key: 'likes', label: 'Likes Received', value: stats?.total_likes ?? 0 },
    { key: 'posts', label: 'Posts Created', value: stats?.post_count ?? 0 },
  ] as const;

  return (
    <div className="nh-card">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between mb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Sparkle size={22} weight="fill" className="text-primary" />
            <h3 className="nh-subtitle">Badges</h3>
          </div>
          <p className="nh-text text-sm">
            Celebrate milestones across posts, recipes, and community love.
          </p>
        </div>
        {isOwnProfile && (
          <button
            onClick={handleRecalculate}
            className="nh-button nh-button-outline flex items-center gap-2 text-sm"
            disabled={recalculating}
            style={{
              opacity: recalculating ? 0.7 : 1,
              cursor: recalculating ? 'wait' : 'pointer',
            }}
          >
            <ArrowClockwise
              size={18}
              className={recalculating ? 'animate-spin' : ''}
            />
            {recalculating ? 'Recalculating...' : 'Recalculate'}
          </button>
        )}
      </div>

      {message && (
        <div
          className="mb-3 px-3 py-2 rounded text-sm"
          style={{
            backgroundColor: 'rgba(59, 130, 246, 0.15)',
            border: '1px solid rgba(59, 130, 246, 0.4)',
            color: 'var(--color-light)',
          }}
        >
          {message}
        </div>
      )}

      {error && (
        <div
          className="mb-3 px-3 py-2 rounded text-sm"
          style={{
            backgroundColor: 'rgba(220, 38, 38, 0.15)',
            border: '1px solid rgba(220, 38, 38, 0.4)',
            color: 'var(--color-error)',
          }}
        >
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-sm nh-text">
          <ArrowClockwise size={18} className="animate-spin" />
          <span>Loading badges...</span>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
            {statBlocks.map((block) => {
              const styles = TYPE_STYLES[block.key] || TYPE_STYLES.default;
              return (
                <div
                  key={block.key}
                  className="rounded-xl p-4 border"
                  style={{
                    background: styles.bg,
                    borderColor: styles.border,
                  }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="nh-text text-xs uppercase tracking-wide">
                      {block.label}
                    </span>
                    <span
                      className="text-xs font-semibold"
                      style={{ color: styles.accent }}
                    >
                      {TYPE_LABELS[block.key] ?? 'Activity'}
                    </span>
                  </div>
                  <div className="text-2xl font-bold" style={{ color: styles.accent }}>
                    {block.value}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div className="flex items-center gap-2 nh-text text-sm">
              <Clock size={16} />
              <span>Last updated: {formatDate(lastUpdated)}</span>
            </div>
            <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--color-light)' }}>
              <Medal size={16} weight="fill" className="text-primary" />
              <span>{badges.length} badge{badges.length === 1 ? '' : 's'} earned</span>
            </div>
          </div>

          {sortedBadges.length === 0 ? (
            <div
              className="rounded-xl border px-4 py-6 text-center"
              style={{
                background: 'rgba(255, 255, 255, 0.02)',
                borderColor: 'var(--forum-search-border)',
              }}
            >
              <p className="nh-text mb-2">No badges yet.</p>
              <p className="text-sm nh-text">
                Share recipes, create posts, and gather likes to start earning badges.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {sortedBadges.map((badge) => {
                const styles = TYPE_STYLES[badge.type] || TYPE_STYLES.default;
                return (
                  <div
                    key={`${badge.type}-${badge.name}-${badge.threshold ?? '0'}`}
                    className="rounded-xl p-4 border h-full"
                    style={{
                      background: styles.bg,
                      borderColor: styles.border,
                    }}
                  >
                    <div className="flex items-start gap-3 mb-2">
                      <div
                        className="w-12 h-12 rounded-lg flex items-center justify-center text-2xl"
                        style={{ backgroundColor: 'rgba(0,0,0,0.15)' }}
                      >
                        {badge.icon || '🏅'}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h4
                            className="font-semibold"
                            style={{ color: 'var(--color-light)' }}
                          >
                            {badge.name}
                          </h4>
                          <span
                            className="text-xs px-2 py-0.5 rounded-full"
                            style={{
                              backgroundColor: 'rgba(0,0,0,0.2)',
                              color: styles.accent,
                              border: `1px solid ${styles.border}`,
                            }}
                          >
                            {TYPE_LABELS[badge.type] ?? 'Badge'}
                          </span>
                        </div>
                        <p className="nh-text text-sm">{badge.description}</p>
                      </div>
                    </div>
                    <div className="flex items-center justify-between text-xs nh-text mt-2">
                      <span>Threshold: {badge.threshold ?? '—'}</span>
                      {badge.earned_at && (
                        <span>Earned at: {formatDate(badge.earned_at)}</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default BadgeShowcase;
