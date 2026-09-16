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

import { Outlet } from 'react-router';
import { SideBar } from './sidebar';

function UserSetting() {
  return (
    // Fills exactly what the app shell leaves below the header, because `main`
    // in the shell is the `1fr` row that is left once the bar is laid out.
    // `min-h-0` on the section and on the content column is what keeps each
    // column's own scroll area scrolling: grid items are `min-height: auto` by
    // default, so a tall child used to stretch the section past the screen and
    // push both the panel's footer and its content out of the viewport instead
    // of scrolling inside it.
    //
    // The content column carries no padding of its own: the panel inside it is
    // meant to sit flush against the rail, the right edge and the bottom edge,
    // which is what its header and body then pad for themselves.
    <section className="grid size-full min-h-0 min-w-0 grid-cols-[4rem_minmax(0,1fr)] grid-rows-1 overflow-hidden md:grid-cols-[303px_minmax(0,1fr)]">
      <SideBar />

      <div className="flex min-h-0 min-w-0 flex-1 overflow-hidden">
        <Outlet />
      </div>
    </section>
  );
}

export default UserSetting;
