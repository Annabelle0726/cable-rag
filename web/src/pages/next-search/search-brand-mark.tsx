/*
 *  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
 *
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 */

import SvgIcon from '@/components/svg-icon';
import { useFetchTokenListBeforeOtherStep } from '@/components/embed-dialog/use-show-embed-dialog';
import { Button } from '@/components/ui/button';
import { SharedFrom } from '@/constants/chat';
import { cn } from '@/lib/utils';
import { Routes } from '@/routes';
import { Send } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useFetchSearchDetail } from '../next-searches/hooks';
import EmbedAppModal from './embed-app-modal';

function EmbedIcon() {
  const [openEmbed, setOpenEmbed] = useState(false);
  const { beta, handleOperate } = useFetchTokenListBeforeOtherStep();

  const { data: SearchData } = useFetchSearchDetail();

  return (
    <>
      <Button
        variant={'outline'}
        onClick={() => {
          handleOperate().then((res) => {
            if (res) {
              setOpenEmbed(!openEmbed);
            }
          });
        }}
      >
        <Send />
      </Button>
      <EmbedAppModal
        open={openEmbed}
        setOpen={setOpenEmbed}
        url={Routes.SearchShare}
        token={SearchData?.id as string}
        from={SharedFrom.Search}
        beta={beta}
      />
    </>
  );
}

/**
 * The search surfaces' brand mark: the same logo file and the same name the app
 * bar and the assistant avatar use, so the search hero cannot drift into showing
 * the upstream wordmark (or a hard-coded teal-to-indigo gradient) again.
 */
export function SearchBrandMark({
  onClick,
  showEmbedIcon = true,
}: {
  onClick?: React.MouseEventHandler<HTMLHeadingElement>;
  showEmbedIcon?: boolean;
}) {
  const { t } = useTranslation();

  return (
    <div className="flex gap-4 items-center">
      <h1
        onClick={onClick}
        className={cn(
          'flex items-center gap-3 text-4xl font-bold text-cable-gradient',
        )}
      >
        <SvgIcon name="brand-logo" width={40} height={40} />
        <span>{t('header.brandShort')}</span>
      </h1>
      {showEmbedIcon && <EmbedIcon></EmbedIcon>}
    </div>
  );
}
