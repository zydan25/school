/* Small progressive enhancement only; Django remains fully functional without JS. */
document.addEventListener("DOMContentLoaded", () => {
  document.documentElement.setAttribute("dir", "rtl");
  const search = document.querySelector("#searchbar");
  if (search) search.setAttribute("placeholder", "ابحث في سجلات الإدارة...");
});
