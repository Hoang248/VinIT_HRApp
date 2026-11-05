'use client';

import * as React from 'react';
import {
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Box,
  Divider,
  Typography,
} from '@mui/material';
import WorkIcon from '@mui/icons-material/Work';
import PeopleIcon from '@mui/icons-material/People';
import BarChartIcon from '@mui/icons-material/BarChart';
import SettingsIcon from '@mui/icons-material/Settings';
import { usePathname, useRouter } from 'next/navigation';
import Link from 'next/link';

const DRAWER_WIDTH = 260;

const menuItems = [
  {
    text: 'Vị trí tuyển dụng',
    icon: <WorkIcon />,
    href: '/positions',
  },
  {
    text: 'Shortlist chia sẻ',
    icon: <PeopleIcon />,
    href: '/shortlist',
  },
  {
    text: 'Báo cáo',
    icon: <BarChartIcon />,
    href: '/dashboard',
  },
  {
    text: 'Quản trị',
    icon: <SettingsIcon />,
    href: '/admin',
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  const isSelected = (href: string) => {
    return pathname.startsWith(href);
  };

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: DRAWER_WIDTH,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: DRAWER_WIDTH,
          boxSizing: 'border-box',
          borderRight: 'none',
          backgroundColor: '#0A2B57',
          color: 'white',
        },
      }}
    >
      {/* Logo Area */}
      <Box sx={{ p: 3, pb: 2 }}>
        <Box
          component="img"
          src="https://data-talent-v2.basecdn.net/careerportalvinuni/logo-footer.png"
          alt="VinUniversity Logo"
          sx={{ height: 40, mb: 2 }}
        />
        <Typography variant="subtitle2" sx={{ color: 'rgba(255,255,255,0.7)', fontSize: 12, textTransform: 'uppercase', letterSpacing: 0.5 }}>
          AI CV Screening
        </Typography>
      </Box>

      <Divider sx={{ borderColor: 'rgba(255,255,255,0.1)' }} />

      {/* Navigation Menu */}
      <List sx={{ pt: 2 }}>
        {menuItems.map((item) => (
          <ListItem key={item.text} disablePadding sx={{ mb: 0.5 }}>
            <ListItemButton
              component={Link}
              href={item.href}
              selected={isSelected(item.href)}
              sx={{
                mx: 1,
                borderRadius: 2,
                '&.Mui-selected': {
                  backgroundColor: '#941616',
                  color: 'white',
                  '&:hover': {
                    backgroundColor: '#7a1212',
                  },
                  '& .MuiListItemIcon-root': {
                    color: 'white',
                  },
                },
                '&:hover': {
                  backgroundColor: 'rgba(255,255,255,0.08)',
                },
              }}
            >
              <ListItemIcon sx={{ color: 'rgba(255,255,255,0.7)', minWidth: 40 }}>
                {item.icon}
              </ListItemIcon>
              <ListItemText
                primary={item.text}
                primaryTypographyProps={{
                  fontSize: 14,
                  fontWeight: 500,
                }}
              />
            </ListItemButton>
          </ListItem>
        ))}
      </List>

      <Box sx={{ flexGrow: 1 }} />

      {/* Footer */}
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)' }}>
          © {new Date().getFullYear()} VinUniversity
          <br />
          Nội bộ sử dụng
        </Typography>
      </Box>
    </Drawer>
  );
}

export { DRAWER_WIDTH };
