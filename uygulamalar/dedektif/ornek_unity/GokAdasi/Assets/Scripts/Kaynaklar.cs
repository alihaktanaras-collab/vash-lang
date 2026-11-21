public static class Kaynaklar
{
    public static int metal = 400;
    public static int yakit = 400;
    public static int kristal = 30;

    public static bool Harca(int m, int y, int k)
    {
        if (metal < m || yakit < y || kristal < k) return false;
        metal -= m; yakit -= y; kristal -= k;
        return true;
    }
}
