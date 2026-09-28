public static class Runner
{
    public static int Main(string[] args)
    {
        return new NUnitLite.AutoRun(typeof(OjolRush.Tests.OjolRushLogicTests).Assembly).Execute(args);
    }
}
