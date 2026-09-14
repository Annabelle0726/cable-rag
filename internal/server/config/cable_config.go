//
//  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
//  Modifications Copyright 2026 线缆工业智搜平台. All Rights Reserved.
//
//  Licensed under the Apache License, Version 2.0 (the "License");
//  you may not use this file except in compliance with the License.
//  You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
//  Unless required by applicable law or agreed to in writing, software
//  distributed under the License is distributed on an "AS IS" BASIS,
//  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//  See the License for the specific language governing permissions and
//  limitations under the License.
//

package config

import (
	"github.com/spf13/viper"
)

// ParseCableConfig reads the cable-domain switch. It is a top-level key in
// conf/service_conf.yaml (`show_cable_only`), mirroring the Python
// `api/db/cable_templates.py` flag, and defaults to false when absent so an
// unmodified deployment keeps serving the official template catalogue.
//
// The environment fallback is RAGFLOW_SHOW_CABLE_ONLY, from the server's
// viper env prefix.
func (c *Config) ParseCableConfig(v *viper.Viper) error {
	c.cableOnly = v.GetBool("show_cable_only")
	return nil
}

// CableOnly reports whether only the cable-domain agent templates may be seeded
// and served, so the service can hide rows seeded before the switch was enabled.
func (c *Config) CableOnly() bool {
	return c.cableOnly
}
