'use client';

import * as React from 'react';
import {
  AppBar,
  Toolbar,
  IconButton,
  InputBase,
  Box,
  Avatar,
  Menu,
  MenuItem,
  Typography,
  Tooltip,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import TranslateIcon from '@mui/icons-material/Translate';
import NotificationsIcon from '@mui/icons-material/Notifications';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

const APPBAR_HEIGHT = 64;

export default function Header() {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [langAnchorEl, setLangAnchorEl] = useState<null | HTMLElement>(null);
  const router = useRouter();
  const menuOpen = Boolean(anchorEl);
  const langOpen = Boolean(langAnchorEl);

  const handleProfileMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleLangMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setLangAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setLangAnchorEl(null);
  };

  const handleLogout = () => {
    localStorage.removeItem('hra_access_token');
    router.push('/');
    handleMenuClose();
  };

  return (
    <AppBar
      position="fixed"
      sx={{
        height: APPBAR_HEIGHT,
        zIndex: (theme) => theme.zIndex.drawer + 1,
        backgroundColor: '#0A2B57',
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
      }}
    >
      <Toolbar sx={{ height: APPBAR_HEIGHT }}>
        {/* Search */}
        <Box sx={{ position: 'relative', flexGrow: 1, maxWidth: 400 }}>
          <SearchIcon
            sx={{
              position: 'absolute',
              left: 12,
              top: '50%',
              transform: 'translateY(-50%)',
              color: '#A09F9C',
              fontSize: 20,
            }}
          />
          <InputBase
            placeholder="Tìm kiếm vị trí, ứng viên..."
            sx={{
              width: '100%',
              backgroundColor: '#F3EEEE',
              borderRadius: '30px',
              pl: 5,
              pr: 2,
              py: 1,
              fontSize: 14,
              color: '#112434',
              transition: 'all 0.2s',
              '&:focus-within': {
                backgroundColor: '#FFFFFF',
                boxShadow: '0 0 0 2px #2599DC',
              },
            }}
          />
        </Box>

        <Box sx={{ flexGrow: 1 }} />

        {/* Language toggle */}
        <Tooltip title="Ngôn ngữ">
          <IconButton
            size="large"
            color="inherit"
            onClick={handleLangMenuOpen}
            sx={{ mx: 0.5 }}
          >
            <TranslateIcon />
          </IconButton>
        </Tooltip>

        {/* Notifications */}
        <Tooltip title="Thông báo">
          <IconButton size="large" color="inherit" sx={{ mx: 0.5 }}>
            <NotificationsIcon />
          </IconButton>
        </Tooltip>

        {/* User avatar */}
        <Tooltip title="Tài khoản">
          <IconButton
            size="small"
            onClick={handleProfileMenuOpen}
            sx={{ ml: 1 }}
          >
            <Avatar
              sx={{
                width: 36,
                height: 36,
                backgroundColor: '#C72127',
                fontSize: 14,
                fontWeight: 'bold',
              }}
            >
              HR
            </Avatar>
          </IconButton>
        </Tooltip>
      </Toolbar>

      {/* User Profile Menu */}
      <Menu
        anchorEl={anchorEl}
        open={menuOpen}
        onClose={handleMenuClose}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        PaperProps={{
          elevation: 2,
          sx: { mt: 1, minWidth: 200, borderRadius: 2 }
        }}
      >
        <MenuItem onClick={handleMenuClose}>
          <Typography variant="body2">Hồ sơ của tôi</Typography>
        </MenuItem>
        <MenuItem onClick={handleMenuClose}>
          <Typography variant="body2">Cài đặt</Typography>
        </MenuItem>
        <MenuItem onClick={handleLogout}>
          <Typography variant="body2" color="error">Đăng xuất</Typography>
        </MenuItem>
      </Menu>

      {/* Language Menu */}
      <Menu
        anchorEl={langAnchorEl}
        open={langOpen}
        onClose={handleMenuClose}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        PaperProps={{
          elevation: 2,
          sx: { mt: 1, minWidth: 150, borderRadius: 2 }
        }}
      >
        <MenuItem onClick={handleMenuClose}>
          <Typography variant="body2" sx={{ fontWeight: 'bold' }}>🇻🇳 Tiếng Việt</Typography>
        </MenuItem>
        <MenuItem onClick={handleMenuClose}>
          <Typography variant="body2">🇬🇧 English</Typography>
        </MenuItem>
      </Menu>
    </AppBar>
  );
}

export { APPBAR_HEIGHT };
