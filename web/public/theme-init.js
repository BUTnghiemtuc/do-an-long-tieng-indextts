// Đặt theme trước khi vẽ trang để không bị nháy màu. File riêng (không inline) vì CSP chỉ cho script 'self'.
(function () {
  var t = null;
  try { t = localStorage.getItem("vidub-theme"); } catch (e) {}
  if (t !== "light" && t !== "dark") t = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  document.documentElement.dataset.theme = t;
})();
