
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.querySelector('[data-menu-toggle]');
  const menu = document.querySelector('[data-menu]');
  if (btn && menu){
    btn.addEventListener('click', () => {
      menu.hidden = !menu.hidden;
    });
  }
});
