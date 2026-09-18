import { Button } from '@/components/ui/button';

import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card';
import { IFile } from '@/interfaces/database/file-manager';
import { Ellipsis } from 'lucide-react';
import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';

/**
 * The knowledge-base cell. Every row gets a capsule — a themed one for each
 * attached knowledge base and a quiet placeholder when nothing is attached —
 * because an empty cell reads as a broken column rather than as "nothing
 * linked yet".
 */
export function KnowledgeCell({ value }: { value: IFile['kbs_info'] }) {
  const { t } = useTranslation('translation', { keyPrefix: 'fileManager' });
  const renderBadges = useCallback((list: IFile['kbs_info'] = []) => {
    return list.map((x) => (
      <span
        key={x.kb_id}
        className="inline-flex shrink-0 items-center rounded-full border border-cable-border-hover bg-cable-nav-active-bg px-2.5 py-0.5 text-xs text-cable-accent"
      >
        {x.kb_name}
      </span>
    ));
  }, []);

  return Array.isArray(value) && value.length ? (
    <section className="flex gap-2 items-center">
      {renderBadges(value?.slice(0, 2))}

      {value.length > 2 && (
        <HoverCard>
          <HoverCardTrigger>
            <Button variant={'ghost'} size={'sm'}>
              <Ellipsis />
            </Button>
          </HoverCardTrigger>
          <HoverCardContent className="flex gap-2 flex-wrap">
            {renderBadges(value)}
          </HoverCardContent>
        </HoverCard>
      )}
    </section>
  ) : (
    // Unlinked file: a translucent glass capsule instead of an empty cell.
    <span className="inline-flex shrink-0 items-center rounded-full border border-cable-hairline bg-glass px-2.5 py-0.5 text-xs text-content-tertiary">
      {t('notLinked')}
    </span>
  );
}
